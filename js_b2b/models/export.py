# -*- coding: utf-8 -*-
from odoo import api, fields, models
from ..base.helper import JSync
from os import path, pardir
from datetime import datetime
from sys import getsizeof
from math import ceil
import psycopg2.extras
import logging

_logger = logging.getLogger('B2B-EXPORT')

class B2BExport(models.Model):
	_name = "b2b.export"
	_sql_constraints = [('res_id_unique', 'unique(res_id)', 'Export res_id needs to be unique!')]
	name = fields.Char(required=True, translate=False, help="Conf item name") 
	res_id = fields.Char(required=True, translate=False, help="Record and model [model_name,record_id]")
	rel_id = fields.Char(required=False, translate=False, help="Related to [model_name,record_id]")

	# ------------------------------------ CUSTOM LOG FILES ------------------------------------

	@api.model
	def write_to_log(self, txt, file, mode="aw+"):
		module_dir = path.abspath(path.join(path.dirname(path.realpath(__file__)), pardir))
		log_file = path.join(module_dir, 'static', 'log', file + '.log')
		with open(log_file, mode) as file:
			date = fields.Datetime.now()
			file.write("%s %s\n" % (date, txt))
			print("%s %s" % (date, txt))

	# ------------------------------------ CUSTOM QUERIES ------------------------------------

	@api.model
	def __pricelists_unique_quantities(self):
		self.env.cr.execute("SELECT pricelist_id, \
			CASE \
				WHEN min_quantity > 0 THEN min_quantity \
				ELSE 1 \
			END min_qty \
			FROM product_pricelist_item  \
			WHERE pricelist_id IS NOT NULL  \
			AND active = true \
			GROUP BY pricelist_id, min_qty \
			ORDER BY pricelist_id, min_qty")
		return self.env.cr.fetchall()

	@api.model
	def __products_in_pricelists(self):
		self.env.cr.execute("SELECT product_tmpl_id \
			FROM product_product \
			WHERE id IN ( \
				SELECT product_id FROM product_pricelist_item \
				WHERE active = true \
				GROUP BY product_id \
			) OR product_tmpl_id IN ( \
				SELECT product_tmpl_id FROM product_pricelist_item \
				WHERE active = true \
				GROUP BY product_tmpl_id \
			) \
			GROUP BY product_tmpl_id")
		return tuple(r[0] for r in self.env.cr.fetchall())

	# ------------------------------------ STATIC METHODS ------------------------------------

	@staticmethod
	def is_time_between(begin_time, end_time, check_time=None):
		# If check time is not given, default to current UTC time
		check_time = check_time or datetime.now().strftime("%H:%M:%S")
		if begin_time < end_time:
			return check_time >= begin_time and check_time <= end_time
		else: # crosses midnight
			return check_time >= begin_time or check_time <= end_time

	# ------------------------------------ PUBLIC METHODS ------------------------------------

	@api.model
	def send_multi(self, object_name, data_list, action_str='replace'):
		"""
		Splits data list in multiple parts if needed and sends it
		"""
		jsync_conf = self.env['b2b.settings'].get_default_params()
		data_parts = list()
		last = 0.0

		# Divide packet if needed
		# large datasets have to be divided in multiple parts
		# determined by packet_size on settings
		packet_size_mb = float(jsync_conf.get('packet_size', 10.0))
		data_size = getsizeof(data_list)/float(1048576)
		num_packets_total = ceil(data_size / packet_size_mb) or 1
		data_items_count = len(data_list)
		avg = data_items_count / float(num_packets_total)

		_logger.info("[send_multi] Tamaño de paquete máximo: %s", packet_size_mb)
		_logger.info("[send_multi] Tamaño de paquete actual: %s", data_size)
		_logger.info("[send_multi] Número de partes a enviar: %s", num_packets_total)

		while last < data_items_count:
			_logger.info("Construyendo parte %i del %i al %i", len(data_parts) + 1, last, last + avg)
			data_parts.append(iter(data_list[int(last):int(last + avg)]))
			last += avg

		# Construct & send packets
		num_packets = len(data_parts)
		for i, part in enumerate(data_parts):
			_logger.info('Enviando parte %i de %i para %s' % (i+1, num_packets, object_name))
			# Make packet
			packet = JSync(self.env, settings=jsync_conf)
			packet.name = object_name
			packet.data = list(part)
			packet.mode = action_str
			packet.part = [i + 1, num_packets]
			packet.send(notify=False, timeout_sec=600)

	def b2b_pricelists_prices(self, test_limit=None, templates_filter=None, pricelists_filter=None, variant=None, operation=None):
		_logger.info('[b2b_pricelists_prices] INICIO!')
		prices = list()
		
		# Out prices
		prices = list()
		# Get decimals number
		prices_precision = self.env['decimal.precision'].precision_get('Product Price')
		# Pricelist quantities search, returns a list of unique quantities for pricelist
		def _search_pricelist_quantities(quantities, pricelist_id):
			unique_quantities = set(tuple(qty[1] for qty in quantities if qty[0] == pricelist_id))
			# Add 1 on quantities if not exists
			if 1 not in unique_quantities:
				unique_quantities.add(1)
			# Return sorted tuple
			return sorted(tuple(unique_quantities))
		# All pricelists or filtered
		pfilter = [('id', 'in', pricelists_filter)] if pricelists_filter else []
		pricelists = tuple(self.env['product.pricelist'].search([('web', '=', True), ('active', '=', True)] + pfilter).mapped(lambda p: (p.id, p.name, p.company_id.id)))
		# Search params, only published products by default
		product_search_params = [('website_published', '=', True)]
		# Limit search to this products
		product_ids = templates_filter or self.__products_in_pricelists()
		product_search_params.append(('id', 'in', product_ids))
		# All filtered products ids
		products_ids = tuple(self.env['product.template'].with_context(active_test=False).search(product_search_params, limit=test_limit).ids)
		# All quantities
		quantities = self.__pricelists_unique_quantities()
		# Log info
		total_pricelists = len(pricelists)
		total_products = len(products_ids)
		product_number = 0.0

		_logger.info('# LISTAS DE PRECIOS: %s' % total_pricelists)
		_logger.info('# PRODUCTOS: %s' % total_products)

		try:
			# For each product
			for product_id in products_ids:
				product_number += 1
				percent = round((product_number / total_products) * 100, 1)
				product = self.env['product.template'].browse(product_id)
				# print("--------------------------------------------------------------------")
				# print(":: %s%% [%s] %s" % (percent, product.default_code, product.name))
				# print("--------------------------------------------------------------------")
				# print(":: %10s\t%10s\t%6s\t%8s" % ('PRICELIST', 'VARIANT', 'QTY', 'PRICE'))
				# For each pricelist
				for pricelist in pricelists:
					# For each quantity
					for min_qty in _search_pricelist_quantities(quantities, pricelist[0]):
						# Product in pricelist & qty context
						# pricelist_id = self.env['product.pricelist'].browse(pricelist[0])
						# self.get_product_price(product, min_qty, False, False)
						product_in_ctx = product.with_context({ 'pricelist': pricelist[0], 'quantity': min_qty })
						# Get all variant prices
						variants_prices = tuple(product_in_ctx.product_variant_ids.mapped('price'))
						# Same price in all variants
						if all(x==variants_prices[0] for x in variants_prices if variants_prices[0]):
							price = None if operation == 'delete' and not variant else round(variants_prices[0], prices_precision)
							# If price is not 0 and not in prices list yet with qty 1
							product_filter = filter(lambda x: x['pricelist_id'] == pricelist[0] and x['product_id'] == product_id and x['variant_id'] == None and x['quantity'] == 1 and x['price'] == price, prices)
							if not bool(list(product_filter)) and (operation == 'delete' or price):
								# print(":: %10s\t%10s\t%6s\t%8s" % (pricelist[0], '-', min_qty, price))
								prices.append({ 
									'company_id': pricelist[2] or None,
									'pricelist_id': pricelist[0],
									'product_id': product_id,
									'variant_id': None,
									'quantity': min_qty,
									'price': price
								})
						else:
							# For each variant
							for v in range(len(variants_prices)):
								variant_id = product_in_ctx.product_variant_ids.ids[v]
								price = None if operation == 'delete' and variant_id == variant else round(variants_prices[v], prices_precision)
								# If price is not 0 and not in prices list yet with qty 1
								product_filter = filter(lambda x: x['pricelist_id'] == pricelist[0] and x['product_id'] == product_id and x['variant_id'] == variant_id and x['quantity'] == 1 and x['price'] == price, prices)
								if not bool(list(product_filter)) and (operation == 'delete' or price):
									# print(":: %10s\t%10s\t%6s\t%8s" % (pricelist[0], variant_id, min_qty, price))
									prices.append({ 
										'company_id': pricelist[2] or None,
										'pricelist_id': pricelist[0],
										'product_id': product_id,
										'variant_id': variant_id,
										'quantity': min_qty,
										'price': price
									})
		except Exception as e:
			_logger.critical('[b2b_pricelists_prices] ERROR EN EL BUCLE! %s' % e)
		finally:
			_logger.info('[b2b_pricelists_prices] FIN!')

		# Send to JSync
		if prices:
			self.write_to_log(str(prices), 'pricelist_item', "a+")
			mode = 'update' if templates_filter is not None else 'replace'
			self.send_multi('pricelist_item', prices, mode)

	def b2b_customers_prices(self, lines_filter=None, operation=None):
		_logger.info('[b2b_customers_prices] INICIO!')
		prices = list()

		# Out prices
		prices = list()
		# Get decimals number
		prices_precision = self.env['decimal.precision'].precision_get('Product Price')
		# Price lines filter
		prices_filter = [('id', 'in', lines_filter)] if lines_filter and type(lines_filter) is list else list()
		try:
			# Get all prices
			for price_line in self.env['customer.price'].read_group(prices_filter, ('company_id', 'partner_id', 'product_tmpl_id', 'product_id', 'min_qty', 'price'), groupby=('company_id', 'partner_id', 'product_tmpl_id', 'product_id', 'min_qty'), orderby=('id DESC'), lazy=False):
				if 'price' in price_line and (price_line.get('product_tmpl_id') or price_line.get('product_id')):
					# Get product ID's
					template_id = price_line['product_tmpl_id'][0] if price_line.get('product_tmpl_id') else None
					variant_id = price_line['product_id'][0] if price_line.get('product_id') else None
					# Unify quantities (0 and 1)
					line_quantity = price_line['min_qty'] if price_line['min_qty'] > 1 else 1
					# If price is related to variant get template id
					if not template_id:
						template_id = self.env['product.product'].browse(variant_id).product_tmpl_id.id
					# Check if rule exists
					price_found = bool(list(filter(lambda x: x['customer_id'] == price_line['partner_id'][0] and x['product_id'] == template_id and x['variant_id'] == variant_id and x['quantity'] == line_quantity, prices)))
					# Add price
					if not price_found and (operation == 'delete' or price_line['price']):
						prices.append({ 
							'company_id': price_line['company_id'][0] if price_line['company_id'] else None,
							'customer_id': price_line['partner_id'][0],
							'product_id': template_id,
							'variant_id': variant_id,
							'quantity': line_quantity,
							'price': round(price_line['price'] if operation != 'delete' else 0, prices_precision)
						})
		except Exception as e:
			_logger.critical('[b2b_customers_prices] ERROR EN EL BUCLE! %s' % e)
		finally:
			_logger.info('[b2b_customers_prices] FIN!')

		# Send to JSync
		if prices:
			self.write_to_log(str(prices), 'customer_price', "a+")
			mode = 'update' if lines_filter is not None else 'replace'
			self.send_multi('customer_price', prices, mode)

	def b2b_products_stock(self, test_limit=None, from_date=None, export_all=None):
		_logger.info('[b2b_products_stock] INICIO!')
		stock = list()

		try:
			# If actual time is between 00:30 & 00:45 set "all" to True
			all_products = export_all or B2BExport.is_time_between('00:30:00', '00:45:00')
			_logger.info('¿STOCK DE TODOS? %s' % all_products)
			stock = self.env['exportxml.object'].compute_product_ids(all=all_products, from_time=from_date, limit=test_limit, inc=1000)
		except Exception as e:
			_logger.critical('[b2b_products_stock] ERROR EN EL BUCLE! %s' % e)
		finally:
			_logger.info('[b2b_products_stock] FIN!')
		
		# Send to JSync
		if stock:
			self.write_to_log(str(stock), 'product_stock', "a+")
			mode = 'replace' if all_products else 'update'
			self.send_multi('product_stock', stock, mode)

	# ------------------------------------ OVERRIDES ------------------------------------

	@api.multi
	def unlink(self):
		for record in self:
			resource_id = record.res_id
			if super(B2BExport, record).unlink():
				# Delete related records also
				self.search([('rel_id', '=', resource_id)]).unlink()
		return True