# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from re import search as validate

# Separadores de email válidos
_partner_email_separators = (',', ';')

class ResPartner(models.Model):
	_inherit = 'res.partner'

	vip_web_access = fields.Many2many('res.company', 'res_partner_res_company_rel', string='VIP Webs Access')

	@api.multi
	def has_valid_emails(self):
		self.ensure_one()

		# Resultados
		results = list()

		# Expresión de validación
		regex = '^[a-z0-9]+[\\._]?[a-z0-9]+[@]\\w+[.]\\w{2,3}$'

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

	@api.onchange('email')
	def _check_email_address(self):
		if self.email:
			if not self.has_valid_emails():
				email_separators_str = ' '.join(['%s' % s for s in _partner_email_separators])
				raise ValidationError(_('Partner email is not valid, check it!\nValid separators: %s') % email_separators_str)
			self.email = self.email.strip()

	@api.multi
	def write(self, vals):
		super(ResPartner, self).write(vals)

		# Comprobar tarifa por compañía
		for record in self:
			partner_pricelists = record.get_field_multicompany('property_product_pricelist')
			pricelists_company_ids = [c[0].id for c in partner_pricelists]
			for company in record.vip_web_access:
				if company.id not in pricelists_company_ids:
					raise ValidationError(_('Unable to set web access for %s\nClient don\'t have pricelist on this company!') % company.name)

		return True
