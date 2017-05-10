import re
import sys
import time
import logging
import openpyxl

logger = logging.getLogger(__name__)


def get_key_from_dictionary(value, dict):
    """
    Finds the key for a given value in a dictionary.
    The value is either a single item or list.
    """
    key = None
    for k, v in dict.items():
        if value == v:
            key = k
            break
        elif type(v) == list and value in v:
            key = k
            break
    return key


def get_attribute_value(obj, attribute):
    """
    Returns the value of a custom JIRA attribute
    """
    value = None if not obj else getattr(obj, attribute)
    return value


def get_products_dict():
    # product_name: [product_code, business_unit, dev_owner, qe_owner]
    try:
        '''
        product_name char(30),
        product_code char(30),
        business_unit char(20),
        dev_owner char(20),
        qe_owner char(20)

        '''

        filename = "product_mapping.xlsx"
        wb = openpyxl.load_workbook(filename)
        sheet = wb.get_sheet_by_name(wb.sheetnames[0])
        line_number = len(sheet["A"])
        print("Filename: ", filename, "Lines: ", line_number)
        dic = {}

        for row in range(1, line_number+1):
            product_name = sheet['A'+str(row)].value.encode('ascii','ignore').strip().decode("UTF-8")
            product_code = sheet['B'+str(row)].value
            business_unit = sheet['C'+str(row)].value
            dev_owner = sheet['D'+str(row)].value
            qe_owner = sheet['E'+str(row)].value

            if product_code:
                product_code = product_code.encode('ascii','ignore').strip().decode("UTF-8")
            else:
                product_code = "NA"

            if business_unit:
                business_unit = business_unit.encode('ascii','ignore').strip().decode("UTF-8")
            else:
                business_unit = "NA"

            if dev_owner:
                dev_owner = dev_owner.encode('ascii','ignore').strip().decode("UTF-8")
            else:
                dev_owner = "NA"

            if qe_owner:
                qe_owner = qe_owner.encode('ascii','ignore').strip().decode("UTF-8")
            else:
                qe_owner = "NA"

            dic[product_name] = [product_code, business_unit, dev_owner, qe_owner]

        return dic
    except:
        print("except")
