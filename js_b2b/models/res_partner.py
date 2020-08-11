# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from re import search as validate
import logging

_logger = logging.getLogger('B2B-RES.PARTNER')

# Separadores de email válidos
_partner_email_separators = (',', ';')

class MergePartner(models.TransientModel):
	_inherit = 'base.partner.merge.automatic.wizard'

	@api.multi
	def action_merge(self):
		packets = list()

		# Partners to unlink
		for partner in self.partner_ids - self.dst_partner_id:
			packets += partner.b2b_record('delete', False, auto_send=False)
		
		super(MergePartner, self).action_merge()

		# Send delete packets
		for packet in packets:
			packet.send(notify=False)

		# Check if new partner is notifiable and trigger actions
		if self.dst_partner_id.is_notifiable_check():
			self.dst_partner_id.b2b_record('create')
		else:
			self.dst_partner_id.b2b_record('delete')

class ResPartner(models.Model):
	_inherit = 'res.partner'

	vip_web_access = fields.Many2many('res.company', 'res_partner_res_company_web_access', string='VIP Webs Access')

	@api.multi
	def __check_vip_web_access_companies_pricelists(self, vals=dict()):
		if vals.get('vip_web_access', False):
			# Comprobar tarifa por compañía web
			# se usa una consulta porque la operación es más rápida que por el ORM
			for record in self:
				self.env.cr.execute("SELECT company_id FROM ir_property WHERE name LIKE 'property_product_pricelist' and res_id = 'res.partner,%s'", (record.id,))
				pricelists_company_ids = [r[0] for r in self.env.cr.fetchall()]
				for company in record.vip_web_access:
					if company.id not in pricelists_company_ids:
						raise ValidationError(_('Unable to set web access for %s\nClient don\'t have pricelist on this company!') % company.name)

	@api.multi
	def has_valid_emails(self):
		self.ensure_one()
		
		# Resultados
		results = list()

		# Expresión PCRE simplificada para validación de email siguiendo la norma RFC822 https://regexr.com/2rhq7
		regex = r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"

		# Si tiene un valor
		if self.email:
			# Por cada separador admitido
			for separator in _partner_email_separators:
				# Si se encuentra el separador
				if separator in self.email:
					emails = self.email.split(separator)
					for one_email in emails:
						email_valid = validate(regex, one_email.strip())
						results.append(email_valid)

		# Si no se encontraron separadores
		if not results and self.email:
			email_valid = validate(regex, self.email)
			results.append(email_valid)

		# Comprobamos si todos los resultados son válidos
		# si no hay resultados significa que no tiene email
		return all(results) if results else False

	@api.multi
	def primary_email(self):
		self.ensure_one()
		
		# Si tiene un valor
		if self.email:
			# Por cada separador admitido
			for separator in _partner_email_separators:
				# Si se encuentra el separador
				if separator in self.email:
					return self.email.split(separator)[0].strip()

		return self.email

	@api.constrains('email')
	def _check_email_address(self):
		for record in self:
			if record.email and not record.has_valid_emails():
				email_separators_str = ' '.join(['%s' % s for s in _partner_email_separators])
				raise ValidationError(_('Partner email is not valid, check it!\nValid separators: %s') % email_separators_str)

	@api.constrains('vip_web_access')
	def __check_vip_web_access_companies_pricelists(self):
		# Comprobar tarifa por compañía web
		# se usa una consulta porque la operación es más rápida que por el ORM
		for record in self:
			if record.vip_web_access:
				self.env.cr.execute("SELECT company_id FROM ir_property WHERE name LIKE 'property_product_pricelist' and res_id = 'res.partner,%s'", (record.id,))
				pricelists_company_ids = [r[0] for r in self.env.cr.fetchall()]
				for company in record.vip_web_access:
					if company.id not in pricelists_company_ids:
						raise ValidationError(_('Unable to set web access for %s\nClient don\'t have pricelist on this company!') % company.name)
