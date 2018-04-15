# -*- coding: utf-8 -*-
# © 2015 Antiun Ingeniería S.L. - Sergio Teruel
# © 2015 Antiun Ingeniería S.L. - Carlos Dauden
# © 2016 Jairo Llopis <jairo.llopis@tecnativa.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    'name': "Product Custom Info",
    'summary': "Add custom field in products",
    'category': 'Customize',
    'version': '10.0.1.0.0',
    'depends': [
        'product',
        'base_custom_info',
    ],
    'data': [
        'views/product_product_view.xml',
        'views/product_template_view.xml',
    ],
    'author': "Tecnativa, "
              "Odoo Community Association (OCA)",
    'website': 'http://www.tecnativa.com',
    'license': 'AGPL-3',
    'installable': True,
}
