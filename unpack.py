import re
from xml.etree import ElementTree


def fix_ns(treeroot):
    """Удаляем паразитные неймспейсы, которые какой-то причине порождаются ElementTree при парсинге выписок"""
    xmlstr = ElementTree.tostring(treeroot).decode()
    xmlstr = re.sub(r'ns\d:', '', xmlstr)
    xmlstr = re.sub(r':ns\d:', '', xmlstr)
    return ElementTree.fromstring(xmlstr)


def get_date(extract_path):
    treeroot = fix_ns(ElementTree.parse(extract_path).getroot())
    target = list(treeroot.iter('Sender'))[0]
    date = target.get('Date_Upload')
    if date:
        return date
    target = list(treeroot.iter('DeclarAttribute'))[0]
    date = target.get('ExtractDate')
    if date:
        date = '-'.join(reversed(date.split('.')))
        return date
    return '0000-00-00'

