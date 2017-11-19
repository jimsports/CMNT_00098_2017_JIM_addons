# -*- coding: utf-8 -*-
# © 2017 Comunitea
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import time
from odoo import _, api, exceptions, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DT_FORMAT


PROCESS_STAGE = 20
DONE_STAGE = 30
NEW_STAGE = 1

class CrmClaim(models.Model):
    _inherit = 'crm.claim'


    @api.depends('claim_line_ids.state', 'claim_line_ids.refund_line_id')
    def _get_invoiced(self):

        for claim in self:

            line_invoice_status = [line for line in claim.claim_line_ids if
                                   line.state != 'draft']
            if not line_invoice_status:
                invoice_status = 'no'
            elif all(x.refund_line_id for x in line_invoice_status):
                invoice_status = 'invoiced'
            elif any(not x.refund_line_id for x in line_invoice_status):
                invoice_status = 'to invoice'
            else:
                invoice_status = 'no'
            claim.invoice_status = invoice_status


    def _get_picking_ids(self):
        """ Search all stock_picking associated with this claim.

        Either directly with claim_id in stock_picking or through a
        procurement_group.

        Or sthrough rma ic claim
        """

        picking_model = self.env['stock.picking']
        for claim in self:
            claim.picking_ids = picking_model.search([
                '|', '|', ('claim_id', 'in', claim.claim_ids.ids),
                ('claim_id', '=', claim.id),
                ('group_id.claim_id', '=', claim.id)
            ])

    @api.depends('stage_id')
    def _get_stage_sequence(self):

        def get_default(stage_id):
            for field in ['default_new', 'default_run', 'default_done']:
                print field
                if stage_id[field]:
                    return field

        for claim in self:
            print "HIHI"
            claim.stage_sequence = get_default(claim.stage_id)


    def _get_invoice_ids(self):
        """ Search all stock_picking associated with this claim.

        Either directly with claim_id in stock_picking or through a
        procurement_group.

        Or sthrough rma ic claim
        """

        picking_model = self.env['account.invoice']
        for claim in self:
            claim.invoice_ids = claim.invoice_id

    # Sequence 1 >> New
    # Sequence 20 >> Process
    # Sequence 30 >> Done
    stage_sequence = fields.Char(compute=_get_stage_sequence)
    partner_id = fields.Many2one(domain=[('is_company','=', True)])
    claim_id = fields.Many2one('crm.claim', "Origin RMA")
    claim_ids = fields.One2many('crm.claim', 'claim_id', "RMA Claim", copy=False)
    invoice_ids = fields.One2many('account.invoice', string='Refunds', compute=_get_invoice_ids, copy=False)
    picking_ids = fields.One2many('stock.picking', string='RMA', compute=_get_picking_ids, copy=False)
    ic = fields.Boolean('Intercompany RMA')
    pick = fields.Boolean('Pick the product in the store', default=True)
    invoice_status = fields.Selection([
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
    ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True)

    def create_IC_RMA(self, auto=True):
        self.ensure_one()
        claim_ids = self.env['crm.claim']
        claim_line_ids = self.claim_line_ids.filtered(lambda x:x.state=='confirmed')
        if not claim_line_ids:
            return claim_ids
        #miro si hay RMA IC >> Si hay artículos de distinta compañia a la compañia
        cmp_ids = claim_line_ids.mapped('product_id').mapped('company_id') - self.company_id
        for company_ in cmp_ids:
            company = company_.sudo()
            company_lines = claim_line_ids.filtered(lambda x: x.product_id.company_id.id == company.id)# and not x.location_dest_id.scrap_location)
            lines_icc = self.env['claim.line']
            lines_icp = self.env['claim.line']
            partner_icp = company.partner_id
            company_icp = self.company_id
            partner_icc = self.company_id.partner_id
            company_icc = company
            if company_lines:
                new_rma_ICP_vals = {'company_id': company_icp.id,
                                'name': self.name + "/ICP",
                                'rma_number': (self.rma_number or self.code) + "/ICP",
                                'claim_type': self.claim_type.return_claim.id,
                                'user_id': self.user_id.id,
                                'partner_id': partner_icp.id,
                                'partner_phone': partner_icp.phone,
                                'email_from': partner_icp.email,
                                'claim_id': self.id,
                                'warehouse_id': self.warehouse_id.id,
                                'ic': True,
                                'pick': True}
                ctx = self._context.copy()
                ctx.update({'force_company': company_icp.id})
                claim_icp = self.env['crm.claim'].with_context().create(new_rma_ICP_vals)

                new_rma_ICC_vals= {'company_id': company_icc.id,
                                'name': self.name + "/ICC",
                                'rma_number': (self.rma_number or self.code) + "/ICC",
                                'claim_type': self.claim_type.id,
                                'user_id': self.user_id.id,
                                'partner_id': partner_icc.id,
                                'partner_phone': partner_icc.phone,
                                'email_from': partner_icc.email,
                                'claim_id': self.id,
                                'warehouse_id': self.warehouse_id.id,
                                'ic': True,
                                'pick': True}
                ctx = self._context.copy()
                ctx.update({'force_company': company_icc.id})
                claim_icc = self.env['crm.claim'].with_context().create(new_rma_ICC_vals)

                for line in company_lines:
                    new_rma_ICC_lines = {'product_id': line.product_id.id,
                                         'unit_sale_price': line.unit_sale_price,
                                         'product_returned_quantity': line.product_returned_quantity,
                                         'location_dest_id': line.location_dest_id,
                                         'company_id': company_icc.id,
                                         'claim_id': claim_icc.id,
                                         'state': 'confirmed'}

                    new_rma_line = self.env['claim.line'].new(new_rma_ICC_lines)
                    new_rma_line._product_id_change()
                    vals = new_rma_line._convert_to_write(new_rma_line._cache)
                    if vals['unit_sale_price'] == 0.00:
                        vals['unit_sale_price'] = line.unit_sale_price
                    new_line_icc = self.env['claim.line'].with_context().create(vals)
                    lines_icc |= new_line_icc
                    new_rma_ICP_lines = {'product_id': line.product_id.id,
                                         'unit_sale_price': line.unit_sale_price,
                                         'product_returned_quantity': line.product_returned_quantity,
                                         'location_dest_id': partner_icp.property_stock_supplier.id,
                                         'company_id': company_icp.id,
                                         'claim_id': claim_icp.id,
                                         'state': 'confirmed'}


                    new_rma_line = self.env['claim.line'].new(new_rma_ICP_lines)
                    new_rma_line._product_id_change()
                    vals = new_rma_line._convert_to_write(new_rma_line._cache)
                    if vals['unit_sale_price'] == 0.00:
                        vals['unit_sale_price'] = line.unit_sale_price
                    new_line_icp = self.env['claim.line'].with_context().create(vals)
                    lines_icp |= new_line_icp
                    trace = False
                    if trace:
                        #MOVIMIENTOS PARA SEGUIMIENTO
                        line.move_in_id.move_dest_id = new_line_icp.move_out_id
                        new_line_icp.move_out_id.move_dest_IC_id = new_line_icc.move_in_id
                        new_line_icc.move_in_id.move_dest_id = line.move_int_id




                    #lines |= (self.env['claim.line'].create(vals))
                claim_icp.claim_line_ids |= lines_icp
                claim_icc.claim_line_ids |= lines_icc
                claim_ids |= claim_icc
                claim_ids |= claim_icp
                claim_icp.make_ic_picking('out', claim_icp.warehouse_id.lot_rma_id, partner_icp.property_stock_supplier)
                #claim_icp.create_RMA_to_stock_pick()
                claim_icc.make_ic_picking('in', partner_icc.property_stock_customer, claim_icc.warehouse_id.lot_rma_id)
                #claim_icc.create_RMA_to_stock_pick()


        return claim_ids

    def RMA_to_stock_pick_vals(self, wh, type='stock'):
        if not wh:
            wh = self.warehouse_id

        location_id = wh.lot_rma_id
        if type != 'out':
            if type == 'stock':
                location_dest_id = wh.lot_stock_id
                picking_type = wh.rma_int_type_id
                action_done_bool = False

            elif type == 'scrap':
                location_dest_id = self.env['stock.location'].search([('scrap_location', '=', True)])[0]
                domain = [('default_location_src_id', '=', location_id.id), ('code','=','internal'), ('default_location_dest_id', '=', location_dest_id.id)]
                picking_type = self.env['stock.picking.type'].search(domain)
                action_done_bool = True
                if not picking_type:
                    raise exceptions.UserError(_('Nos picking type for scrap rma found'))

            else:
                location_dest_id = wh.lot_rma_id
                picking_type = wh.rma_int_type_id
                action_done_bool = True
        else:
            picking_type = wh.rma_out_type_id
            location_dest_id = self.partner_id.property_stock_supplier
            action_done_bool = True
        vals = {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'picking_type_id': picking_type.id,
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'origin': self.code,
            'state': 'draft',
            'date': time.strftime(DT_FORMAT),
            'note': 'RMA picking {}'.format(type),
            'claim_id': self.id,
            'action_done_bool': action_done_bool
        }
        return vals

    def RMA_to_stock_pick_line_vals(self, picking, line):
        return {
             'name': line.product_id.display_name,
             'priority': '0',
             'date': time.strftime(DT_FORMAT),
             'date_expected': time.strftime(DT_FORMAT),
             'product_id': line.product_id.id,
             'product_uom_qty': line.product_returned_quantity,
             'product_uom': line.product_id.uom_id.id,
             'partner_id': picking.partner_id.id,
             'picking_id': picking.id,
             'state': 'draft',
             'price_unit': line.unit_sale_price,
             'company_id': picking.company_id.id,
             'location_id': picking.location_id.id,
             'location_dest_id': line.location_dest_id.id,
             'note': 'RMA picking {}'.format(type),
         }

    def create_rma_pick(self, wh, type, moves):
        if self.env.user.company_id == self.company_id:
            ctx = False
        else:
            ctx = self._context.copy()
            ctx.update({'force_company': self.company_id.id})
        pick_vals = self.RMA_to_stock_pick_vals(wh, type)
        if ctx:
            pick = self.env['stock.picking'].sudo().with_context(ctx).create(pick_vals)
        else:
            pick = self.env['stock.picking'].create(pick_vals)

        for move in moves:
            move_vals = self.RMA_to_stock_pick_line_vals(pick, move)
            if ctx:
                stock_move = self.env['stock.move'].sudo().with_context(ctx).create(move_vals)
            else:
                stock_move = self.env['stock.move'].create(move_vals)
            if stock_move:

                move.write({'move_int_id': stock_move.id,
                            'state': 'treated'})
                #PARA SEGUIMIENTO
                # trace = False
                # if trace:
                #    move.move_in_id.move_dest_id = stock_move.id
                    
        pick.action_confirm()

        return pick

    def create_RMA_to_stock_pick(self):
        pick_ids = self.env['stock.picking']
        for claim_id in self:
            domain = [('claim_id', '=', claim_id.id),
                      ('move_int_id', '=', False),
                      ('move_out_id', '=', False),
                      ('move_in_id', '!=', False),
                      ('state', '=', 'confirmed')
                      ]

            stock_domain = domain + [('product_id.company_id', '=', claim_id.company_id.id)]
            moves = self.env['claim.line'].search(stock_domain)
            if moves:
                stock_moves = moves.filtered(lambda x: not x.location_dest_id.scrap_location)
                loc_stock = stock_moves.mapped('location_dest_id')

                scrap_moves = moves.filtered(lambda x: x.location_dest_id.scrap_location)
                lot_scrap = scrap_moves.mapped('location_dest_id')

                for loc in loc_stock:
                    wh_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', loc.id)])
                    stock_pick = claim_id.create_rma_pick(wh_id, 'stock', stock_moves.filtered(lambda x:x.location_dest_id.id == loc.id))
                    pick_ids |= stock_pick

                for loc in lot_scrap:
                    wh_id = claim_id.warehouse_id
                    stock_pick = claim_id.create_rma_pick(wh_id, 'scrap', scrap_moves.filtered(lambda x:x.location_dest_id.id == loc.id))
                    pick_ids |= stock_pick

        return pick_ids

    def make_ic_picking(self, picking_type='in', location_id=False, location_dest_id=False):

        self.ensure_one()
        ctx = self._context.copy()
        ctx.update({'picking_type': 'in',
                    'product_return': True,
                    'force_company': self.company_id.id,
                    'company_id': self.company_id.id,
                    'partner_id': self.partner_id.id,
                    'active_id': self.id,
                    'active_ids': [self.id]})

        new_wzd = self.env['claim_make_picking.wizard'].with_context(ctx).create({})
        if location_dest_id:
            new_wzd.claim_line_dest_location_id = location_dest_id
        if location_id:
            new_wzd.claim_line_source_location_id = location_id
        new_wzd.sudo()._create_picking(self, picking_type)


    def _stage_find(self, state=False,team_id=False,name=False,domain=[], order='sequence'):
        if state:
            domain += [('default_%s'%state, '=', True)]
        if team_id:
            domain += [('team_id', '=', False)]
        if name:
            domain += [('name','=',False)]

        # perform search, return the first found
        crm_stage = self.env['crm.claim.stage'].search(domain, order=order, limit=1)
        return crm_stage and crm_stage.id or False