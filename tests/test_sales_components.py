"""Independent products, zero-degree prescriptions and frame/lens association QC."""

from datetime import datetime, timedelta
import pytest
from app.constants import INDIA
from app.customer_schemas import PrescriptionInput
from app.domain.models import EyePower
from app.services.pairing import frame_lens_pairs
from app.services.prescriptions import validate_lens
from test_stage4 import basic_meta, lens, rx, TODAY
from test_production_matrix import production_env, identity_template, backend


# Entry and billing must agree on the inclusive zero-to-180-degree grid.
@pytest.mark.parametrize("axis,valid", [(0, True), (5, True), (180, True), (-5, False), (1, False), (185, False)])
def test_axis_boundaries_match_entry_and_billing(basic_meta, axis, valid):
    body={"phone":"9000000005","valid_until":"2027-10-26",
          "od":{"sph":-2,"cyl":0,"axis":axis,"add":0},
          "os":{"sph":-2,"cyl":0,"axis":axis,"add":0}}
    if valid:
        PrescriptionInput(**body)
    else:
        with pytest.raises(ValueError):
            PrescriptionInput(**body)
    result=validate_lens(rx(right=EyePower("-2","0",axis,"0"),left=EyePower("-2","0",axis,"0")),lens(basic_meta),basic_meta,on_date=TODAY)
    assert result.valid == valid


# Grouped API selections and adjacent browser selections retain their association.
@pytest.mark.parametrize("kinds,optical,expected", [
    (["frame","frame","lens","lens"], [0,1], [(0,2),(1,3)]),
    (["frame","lens","frame","lens"], [0,2], [(0,1),(2,3)]),
    (["frame","frame","lens"], [1], [(1,2)]),
])
def test_frame_pairing_contracts(kinds,optical,expected):
    assert frame_lens_pairs(kinds,optical)==expected


# A frame-only bill intentionally has no lens or prescription and still restocks correctly.
def test_explicit_frame_only_sale_and_refund(production_env):
    clients,store,source,_=production_env
    stock=source.stock(92000003,70000002)
    sale=clients("cashier").post('/sales/prepare',json={
        "phone":"9000000003","store_code":"HSR","staff_id":"S105","variant_ids":[],
        "members":[{"phone":"9000000003","frame_only_variant_ids":[91000003]}],
        "selected_offer_id":"FESTIVE10",
    })
    assert sale.status_code==200,sale.text
    identifier=sale.json()['checkout_id'];quote=store.load_quote(identifier)
    assert len(quote['lines'])==1 and quote['lines'][0]['rx_id'] is None
    complete=clients('cashier').post(f'/sales/{identifier}/complete')
    assert complete.status_code==200,complete.text
    assert source.stock(92000003,70000002)==stock-1
    refund=clients('manager').post('/refunds/prepare',json={'checkout_id':identifier,'reason':'Frame-only return'})
    assert refund.status_code==200,refund.text
    result=clients('manager').post('/refunds/'+refund.json()['refund_id']+'/complete')
    assert result.status_code==200 and source.stock(92000003,70000002)==stock


# A confirmed zero-axis prescription must be attached to the lens invoice line.
def test_clinical_zero_axis_lens_only_quote(production_env):
    clients,store,_,_=production_env
    clinical=clients('optometrist').post('/api/prescriptions',json={
        'phone':'9000000005','valid_until':(datetime.now(INDIA).date()+timedelta(days=365)).isoformat(),
        'od':{'sph':-2,'cyl':0,'axis':0,'add':1.5},'os':{'sph':-2,'cyl':0,'axis':0,'add':1.5},
    })
    assert clinical.status_code==200,clinical.text
    sale=clients('cashier').post('/sales/prepare',json={
        'phone':'9000000005','store_code':'HSR','staff_id':'S105','variant_ids':[],
        'members':[{'phone':'9000000005','lens_only_variant_ids':[91000083]}],
    })
    assert sale.status_code==200,sale.text
    assert store.load_quote(sale.json()['checkout_id'])['lines'][0]['rx_id']==clinical.json()['rx_id']
    admin_clinical=clients('admin').post('/api/prescriptions',json={
        'phone':'9000000005','store_code':'HSR',
        'valid_until':(datetime.now(INDIA).date()+timedelta(days=365)).isoformat(),
        'od':{'sph':-2,'cyl':0,'axis':0,'add':1.5},'os':{'sph':-2,'cyl':0,'axis':0,'add':1.5},
    })
    assert admin_clinical.status_code==200,admin_clinical.text
    with store._connect() as db:
        saved=db.execute('SELECT store_code,created_by FROM prescriptions WHERE rx_id=?',(admin_clinical.json()['rx_id'],)).fetchone()
    assert saved['store_code']=='HSR' and saved['created_by']=='admin'


# The frame-only field cannot bypass prescription validation on a lens variant.
def test_frame_only_rejects_lens_variants(production_env):
    clients,_,_,_=production_env
    response=clients('cashier').post('/sales/prepare',json={
        'phone':'9000000004','store_code':'HSR','staff_id':'S105','variant_ids':[],
        'members':[{'phone':'9000000004','frame_only_variant_ids':[91000083]}],
    })
    assert response.status_code==422 and 'frame variants' in response.text
