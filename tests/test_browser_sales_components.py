"""Cashier-visible independent products and invoice/payment recovery in Chrome."""

import os
import csv
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_browser_coupons import coupon_app, production_env, identity_template, backend, private_source


# Use the inline lens dropdowns in the order shown to store staff.
def choose_lens(page, lens_type='progressive', index='1.6', coating='blue_cut'):
    for selector,value in [('#lens-type',lens_type),('#lens-index',index),('#lens-coating',coating)]:
        page.locator(selector).select_option(value)
        page.wait_for_function('!state.busy')


# Keep every transition through the same visible controls available to a cashier.
def add_wearer(page, phone='9000000005'):
    page.locator('#customer-form input[name=phone]').fill(phone)
    page.get_by_role('button',name='Add wearer').click()
    page.wait_for_function('!state.busy && state.cart.members.length === 1')


# Build a validated quote and fail immediately on any API business-rule rejection.
def review(page):
    with page.expect_response(lambda response: response.url.endswith('/sales/prepare')) as pending:
        page.locator('[data-action="prepare-sale"]').click()
    assert pending.value.status==200,pending.value.text()
    page.wait_for_function('!state.busy && state.quote !== null')
    return pending.value.json()


# Prove line removal, separate lenses, credit-free pricing and cash recovery through invoices.
def test_independent_products_cart_and_invoices(coupon_app):
    base,store,source=coupon_app
    errors=[]
    screenshots=Path('runtime/qc/screenshots');screenshots.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel=os.environ.get('ELUNO_BROWSER_CHANNEL','chrome') or None,headless=True)
        try:
            page=browser.new_page(viewport={'width':1440,'height':1050})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base)
            page.locator('input[name=username]').fill('manager')
            page.locator('input[name=password]').fill('Acceptance-password-2026!')
            page.get_by_role('button',name='Sign in to Store Studio').click()
            page.locator('[data-page="billing"]').wait_for()
            page.locator('[data-page="billing"]').click();page.wait_for_function('!state.busy')
            add_wearer(page)
            page.locator('[data-product="91000003"]').click();page.wait_for_function('!state.busy')
            assert page.locator('#lens-type').is_visible()
            assert page.evaluate('state.cart.members[0].frame_only_variant_ids')==[91000003]

            # A separately purchased lens must not consume the waiting frame.
            page.locator('#lens-target').select_option('lens_only');page.wait_for_function('!state.busy')
            choose_lens(page,'single_vision','1.67','blue_cut')
            page.locator('[data-action="add-lens-only"]').click();page.wait_for_function('!state.busy')
            assert page.evaluate('state.cart.members[0].lens_only_variant_ids')==[91000055]
            assert page.evaluate('state.cart.members[0].frame_only_variant_ids')==[91000003]
            # Different lenses must not jointly satisfy a single lens coupon's conditions.
            page.locator('[data-configure-frame="0"]').click();page.wait_for_function('!state.busy')
            choose_lens(page,'progressive','1.5','standard')
            page.locator('[data-action="add-configured-pair"]').click();page.wait_for_function('!state.busy')
            assert 'FREE_BLUECUT_PGX' not in page.locator('#offer-code option').evaluate_all('options=>options.map(option=>option.value)')
            page.locator('[data-remove-pair="0"]').click();page.wait_for_function('!state.busy')
            page.locator('[data-category="frame"]').click();page.wait_for_function('!state.busy')
            page.locator('[data-product="91000003"]').click();page.wait_for_function('!state.busy')
            page.locator('[data-remove-lens-only="0"]').click();page.wait_for_function('!state.busy')

            # Attaching a lens moves the existing frame into one pair, without duplicating it.
            page.locator('[data-configure-frame="0"]').click();page.wait_for_function('!state.busy')
            choose_lens(page)
            page.locator('[data-action="add-configured-pair"]').click();page.wait_for_function('!state.busy')
            assert page.evaluate('state.cart.members[0].variant_ids')==[91000003,91000083]
            assert page.evaluate('state.cart.members[0].frame_only_variant_ids')==[]
            if source.stock(92000003,70000002)>=2:
                page.locator('[data-category="frame"]').click();page.wait_for_function('!state.busy')
                page.locator('[data-product="91000003"]').click();page.wait_for_function('!state.busy')
                choose_lens(page)
                page.locator('[data-action="add-configured-pair"]').click();page.wait_for_function('!state.busy')
                assert page.evaluate('state.cart.members[0].variant_ids')==[91000003,91000083,91000003,91000083]
                page.locator('[data-remove-pair="2"]').click();page.wait_for_function('!state.busy')
                assert page.evaluate('state.cart.members[0].variant_ids')==[91000003,91000083]
            page.locator('[data-remove-pair-lens="0"]').click();page.wait_for_function('!state.busy')
            assert page.evaluate('state.cart.members[0].frame_only_variant_ids')==[91000003]
            assert page.evaluate('state.cart.members[0].variant_ids')==[]
            page.locator('[data-remove-frame-only="0"]').click();page.wait_for_function('!state.busy')
            assert page.locator('[data-action="prepare-sale"]').is_disabled()

            # The all-dropdown lens-only flow reaches a card invoice without moving frame stock.
            stock=source.stock(92000003,70000002)
            choose_lens(page)
            page.screenshot(path=str(screenshots/'sales-lens-dropdowns.png'),full_page=True)
            page.locator('[data-action="add-lens-only"]').click();page.wait_for_function('!state.busy')
            codes=page.locator('#offer-code option').evaluate_all('options=>options.map(option=>option.value)')
            assert 'FESTIVE10' not in codes and 'BUNDLE300' not in codes
            page.locator('#payment-method').select_option('card');page.wait_for_function('!state.busy')
            quote=review(page)
            assert quote['total_paise']==949900
            page.locator('[data-action="complete-sale"]').click()
            page.locator('dialog[open] .receipt').wait_for();page.wait_for_function('!state.busy')
            checkout=store.get_checkout(quote['checkout_id'])
            order=source.order_by_id(checkout['shopify_order_id'])
            assert len(order['line_items'])==1 and source.stock(92000003,70000002)==stock
            assert store.load_quote(quote['checkout_id'])['lines'][0]['rx_id']
            assert checkout['checkout_elapsed_ms'] is not None
            page.screenshot(path=str(screenshots/'lens-only-invoice.png'),full_page=True)
            page.get_by_role('button',name='Close ✕',exact=True).click();page.wait_for_function('!state.busy')
            assert page.locator('[data-action="complete-sale"]').count()==0
            page.locator('.nav-button[data-page="reports"]').click();page.wait_for_function('!state.busy')
            with page.expect_download() as pending_download:
                page.locator('[data-action="download-day-end"]').click()
            download=pending_download.value
            download.save_as('runtime/qc/downloaded-day-end.csv')
            with open('runtime/qc/downloaded-day-end.csv',newline='',encoding='utf-8') as handle:
                exported=list(csv.DictReader(handle))
            assert exported[0]['store']=='HSR' and exported[0]['bill_count']=='1'
            assert exported[0]['card_inr']=='9499.00'
            page.locator('.nav-button[data-page="transactions"]').click();page.wait_for_function('!state.busy')

            # Ready sunglasses require no lens, and a failed cash confirmation preserves the bill.
            page.locator('[data-action="new-sale"]').click();page.wait_for_function('!state.busy')
            add_wearer(page,'9000000003')
            page.locator('[data-category="sunglasses"]').click();page.wait_for_function('!state.busy')
            page.locator('.product:not([disabled])').first.click()
            page.locator('[data-action="add-ready-sunglasses"]').click();page.wait_for_function('!state.busy')
            page.locator('#payment-method').select_option('cash');page.wait_for_function('!state.busy')
            cash_quote=review(page)
            page.locator('[data-action="complete-sale"]').click()
            page.locator('dialog[open] .receipt').wait_for();page.wait_for_function('!state.busy')
            pending=store.get_checkout(cash_quote['checkout_id'])
            assert pending['status']=='draft' and pending['payment_charge_id'] is None
            page.get_by_role('button',name='Close ✕',exact=True).click();page.wait_for_function('!state.busy')
            page.locator('[data-page="till"]').click();page.wait_for_function('!state.busy')
            page.locator('#open-till-form input[name=amount]').fill('1000')
            page.locator('#open-till-form button').click();page.wait_for_function('!state.busy')
            page.locator('[data-page="transactions"]').click();page.wait_for_function('!state.busy')
            page.locator(f'[data-detail="{cash_quote["checkout_id"]}"]').first.click()
            page.locator('[data-action="complete-detail"]').click();page.wait_for_function('!state.busy')
            assert store.get_checkout(cash_quote['checkout_id'])['status']=='order_recorded'
            # Prescription sunglasses reuse the same lens choices and carry a zero-axis Rx snapshot.
            page.get_by_role('button',name='Close ✕',exact=True).click();page.wait_for_function('!state.busy')
            page.locator('[data-action="new-sale"]').click();page.wait_for_function('!state.busy')
            add_wearer(page)
            page.locator('[data-category="sunglasses"]').click();page.wait_for_function('!state.busy')
            page.locator('[data-product="91000017"]').click()
            page.locator('[data-action="configure-sunglasses-rx"]').click();page.wait_for_function('!state.busy')
            choose_lens(page)
            page.locator('[data-action="add-configured-pair"]').click();page.wait_for_function('!state.busy')
            sunglasses_quote=review(page)
            page.locator('[data-action="complete-sale"]').click()
            page.locator('dialog[open] .receipt').wait_for();page.wait_for_function('!state.busy')
            recorded=store.get_checkout(sunglasses_quote['checkout_id'])
            assert recorded['status']=='order_recorded'
            submitted=store.get_invoice(sunglasses_quote['checkout_id'])['order_submission_json']
            import json
            lens_line=json.loads(submitted)['line_items'][1]
            snapshot=json.loads(next(item['value'] for item in lens_line['properties'] if item['name']=='rx_snapshot'))
            assert snapshot['od']['axis']==0 and snapshot['os']['axis']==0
            assert not errors,errors
        finally:
            browser.close()
