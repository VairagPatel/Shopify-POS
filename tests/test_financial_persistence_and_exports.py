"""Issued invoice, refund synchronization and downloadable Shopify report acceptance."""

import csv
import io
import json
from decimal import Decimal
import pytest
from app.operations import store_day
from app.persistence.sqlite import SQLiteStore
from app.services.reporting import DayEndService
from test_production_matrix import production_env, identity_template, backend


# Complete one real mocked terminal charge and order with an explicitly selected coupon.
def paid_sale(clients):
    client=clients('cashier')
    quote=client.post('/sales/prepare',json={
        'phone':'9000000004','store_code':'HSR','staff_id':'S105',
        'variant_ids':[91000003,91000083],'selected_offer_id':'FESTIVE10',
    })
    assert quote.status_code==200,quote.text
    completed=client.post('/sales/'+quote.json()['checkout_id']+'/complete')
    assert completed.status_code==200,completed.text
    return quote.json(),completed.json()


# Paid invoices must be immutable, line-queryable and linked to the exact submitted order.
def test_invoice_and_refund_remain_queryable_and_idempotent(production_env):
    clients,store,source,_=production_env
    quote,checkout=paid_sale(clients)
    invoice=store.get_invoice(quote['checkout_id'])
    assert invoice and invoice['invoice_no']==quote['invoice_no']
    assert invoice['shopify_order_id']==checkout['shopify_order_id']
    assert invoice['total_paise']==quote['total_paise']
    assert invoice['gross_paise']-invoice['discount_paise']==invoice['taxable_paise']+invoice['tax_paise']
    submitted=json.loads(invoice['order_submission_json'])
    assert submitted['transactions'][0]['kind']=='sale'
    assert submitted['transactions'][0]['status']=='success'
    assert int(Decimal(submitted['transactions'][0]['amount'])*100)==quote['total_paise']
    properties={item['name']:item['value'] for item in submitted['line_items'][1]['properties']}
    assert properties['rx_id'] and submitted['line_items'][1]['tax_lines']
    assert json.loads(properties['rx_snapshot'])['rx_id']==properties['rx_id']
    assert 'axis' in json.loads(properties['rx_snapshot'])['od']
    assert checkout['shopify_order_id']!=invoice['invoice_no']
    repeated=clients('cashier').post('/sales/'+quote['checkout_id']+'/complete')
    assert repeated.status_code==200
    with store._connect() as db:
        assert db.execute('SELECT COUNT(*) FROM invoices').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM invoice_lines').fetchone()[0]==2
        # Simulate an older completed checkout that did not yet have an invoice snapshot.
        db.execute('DELETE FROM invoices')
    restored=SQLiteStore(store.path)
    assert restored.get_invoice(quote['checkout_id'])['total_paise']==quote['total_paise']
    refund=clients('manager').post('/refunds/prepare',json={'checkout_id':quote['checkout_id'],'reason':'Invoice QC return'})
    assert refund.status_code==200,refund.text
    result=clients('manager').post('/refunds/'+refund.json()['refund_id']+'/complete')
    assert result.status_code==200,result.text
    recorded=result.json()
    assert recorded['status']=='recorded' and recorded['synced_at'] and recorded['shopify_refund_id']
    with store._connect() as db:
        events=[row['status'] for row in db.execute('SELECT status FROM refund_events WHERE refund_id=? ORDER BY event_id',(recorded['refund_id'],))]
    assert events==['prepared','terminal_pending','terminal_refunded','shopify_pending','recorded']
    order=source.order_by_id(checkout['shopify_order_id'])
    assert str(order['refunds'][0]['id'])==recorded['shopify_refund_id']
    assert restored.get_invoice(quote['checkout_id']) is not None


# CSV must reconcile exactly to the independent original Must day-end API.
def test_downloaded_day_end_matches_source_api(production_env):
    clients,_,source,_=production_env
    quote,checkout=paid_sale(clients)
    day=store_day(source.order_by_id(checkout['shopify_order_id'])['created_at'])
    report=clients('cashier').get('/reports/day-end',params={'date':day,'store_code':'HSR'})
    assert report.status_code==200,report.text
    data=report.json()
    export=clients('cashier').get('/api/reports/export',params={'day':day,'basis':'day_end'})
    assert export.status_code==200 and 'attachment' in export.headers['content-disposition']
    records=list(csv.DictReader(io.StringIO(export.text)))
    assert len(records)==1 and records[0]['store']=='HSR'
    row=records[0]
    assert int(row['bill_count'])==data['bill_count']
    for field in ('gross','taxable','tax','discounts','refunds','net_collected'):
        assert Decimal(row[field+'_inr'])*100==data[field+'_paise']
    assert Decimal(row['upi_inr'])*100==quote['total_paise']
    assert row['source']=='Shopify orders'
    assert Decimal(row['taxable_inr'])+Decimal(row['tax_inr'])==Decimal(row['gross_inr'])-Decimal(row['discounts_inr'])
    central=clients('finance').get('/api/reports/export',params={'day':day,'basis':'daily'})
    assert central.status_code==200
    stores=list(csv.DictReader(io.StringIO(central.text)))
    assert len(stores)==8 and stores[-1]['store']=='ALL'
    assert sum(int(row['bill_count']) for row in stores[:-1])==int(stores[-1]['bill_count'])
    assert clients('cashier').get('/api/reports/export',params={'day':day,'store_code':'IN'}).status_code==403
    assert clients('cashier').get('/api/reports/export',params={'day':day,'basis':'unknown'}).status_code==422


# Failed refunds are not cash movements and must not inflate day-end refund figures.
def test_day_end_ignores_failed_refund_transactions():
    class Source:
        # Provide one store on a stable reporting date.
        def locations(self):
            return [{'id':1,'kind':'store','store_code':'HSR'}]
        # Provide successful and failed reversals on the same recorded order.
        def orders(self,limit):
            return [{'id':1,'location_id':1,'created_at':'2026-10-26T12:00:00+05:30','cancelled':False,
                     'total_paise':10000,'lines':[{'gross_paise':10000,'discount_paise':0,'tax_paise':500}],
                     'payments':[{'kind':'sale','status':'success','method':'upi','amount_paise':10000}],
                     'refunds':[{'payments':[{'kind':'refund','status':'failure','amount_paise':5000},
                                               {'kind':'refund','status':'success','amount_paise':1000}]}]}]
    result=DayEndService(Source()).report('HSR','2026-10-26')
    assert result['refunds_paise']==1000 and result['net_collected_paise']==9000
