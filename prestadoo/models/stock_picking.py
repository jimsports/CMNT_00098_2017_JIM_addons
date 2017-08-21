# -*- coding: utf-8 -*-
from .pd_base import BaseExtClass
from .. import tools


class StockMove(BaseExtClass):
    _inherit = "stock.picking"

    fields_to_watch = ('id', 'partner_id', 'name', 'date_done', 'amount_total', 'state')

    def is_notifiable(self):
        return self.picking_type_id.code == "outgoing" and self.state == "done" and self.partner_id.is_notifiable()

    def set_props(self, unlink=False):
        podocuments = """
                <podocuments>
                  <IdDocs>{}</IdDocs>
                  <CardCode>{}</CardCode>
                  <ObjType>{}</ObjType>
                  <DocEntry>{}</DocEntry>
                  <DocNum>{}</DocNum>
                  <DocDate>{}</DocDate>
                  <DocTotal>{}</DocTotal>
                </podocuments>
            """

        self.xml = podocuments.format(
            "15#" + str(self.id),                               # IdDocs
            self.partner_id.commercial_partner_id.ref or self.partner_id.commercial_partner_id.id,          # CardCode
            "15",                                               # ObjType --> 15 = Albarán de ventas
            self.id,                                            # DocEntry
            self.name,                                          # DocNum
            tools.format_date(self.date),                       # DocDate
            self.amount_total                                   # DocTotal
        )

        self.obj_type = 'DOCUMENTS'
