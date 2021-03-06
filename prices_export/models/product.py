# -*- coding: utf-8 -*-
# © 2020 Comunitea - Javier Colmenero <javier@comunitea.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import fields, models, api, _
from datetime import datetime

import logging
_logger = logging.getLogger('--EXPORTACIÓN PRECIOS--')



class ProductTemplate(models.Model):

    _inherit = 'product.template'
  
    @api.multi
    def write(self, vals):
        if 'categ_id' in vals:
            self.set_template_categ_update(vals['categ_id'])
        return super(ProductTemplate, self).write(vals)
    
    @api.model
    def create(self, vals):
        res = super(ProductTemplate, self).create(vals)
        if 'categ_id' in vals:
            res.set_template_categ_update(vals['categ_id']) 
        return res
    
    @api.multi
    def set_template_categ_update(self, new_categ_id):
        """
        Busco los productos de la plantilla, y lanzo los cálculos bajo demanda
        de para esos prodtos eb los items de la vieja y nueva categoría
        """
        for tmpl in self:
            domain = [('product_tmpl_id', '=', tmpl.id)]
            products = self.env['product.product'].search(domain)
            products.set_items_categ_update(new_categ_id)

class ProductProduct(models.Model):

    _inherit = 'product.product'
  
    @api.multi
    def write(self, vals):
        if 'active' in vals and vals['active'] == True:
            self.set_items_update()
        if 'categ_id' in vals:
            self.set_items_categ_update(vals['categ_id'])
        return super(ProductProduct, self).write(vals)

    @api.multi
    def set_items_update(self):
        """
        Busco los items donde está involucrado y cambio el write date para
        lanzar el recálculo.
        Como al recalcular buscará las tarifas que dependen de la suya evito
        traerme reglas que se basan en otra tarifa.
        Se supone que el precio de todos los productos se los da una tarifa
        base.
        """
        domain = [
            '&',
            '&',
            ('pricelist_id.to_export', '=', True),
            ('base_pricelist_id', '=', False),
            '|','|',
            ('product_id', 'in', self._ids),
            ('product_tmpl_id', 'in', self.mapped('product_tmpl_id')._ids),
            ('categ_id', 'in', self.mapped('categ_id')._ids),

        ]
        items = self.env['product.pricelist.item'].search(domain)
        if items:
            # Actualizo el write date para que lo encuentre el cron la siguiente
            # vez
            _logger.info('Marcando items para actualizar después')
            items.write({'last_update': fields.Datetime.now()})
        return
    
    @api.multi
    def set_items_categ_update(self, new_categ_id):
        """
        Busco los items donde está involucrado y cambio el write date para
        lanzar el recálculo.
        """
        _logger.info('Exportando precios bajo demanda (CAMBIO DE CATEGORÍA)')
        for product in self:
            domain = [
                ('pricelist_id.to_export', '=', True),
                ('categ_id', 'in', [product.categ_id.id, new_categ_id]),
            ]
            items = self.env['product.pricelist.item'].search(domain)
            if items:
                # Actualizo el write date para que lo encuentre el cron la siguiente
                # vez
                _logger.info('Marcando items para actualizar después')
                items.write({'last_update': fields.Datetime.now()})
        return