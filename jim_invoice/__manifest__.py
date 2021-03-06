# -*- coding: utf-8 -*-
# © 2016 Comunitea - Santi Argüeso<santi@comunitea.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    'name': 'Jim Invoice',
    'version': '10.0.1.0.0',
    'author': 'Comunitea ',
    "category": "Custom",
    'license': 'AGPL-3',
    'depends': [
        'account_payment_partner',
        'sale',
        'purchase',
        'account_financial_report_qweb'
    ],
    'contributors': [
        "Comunitea ",
        "Santi Argüeso <santi@comunitea.com>",

    ],
    "data": [
        'views/sale_order.xml',
        'views/purchase_order.xml',
    ],
    "installable": True
}
