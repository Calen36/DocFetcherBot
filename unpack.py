import re
from xml.etree import ElementTree


def fix_ns(treeroot):
    """Удаляем паразитные неймспейсы, которые какой-то причине порождаются ElementTree при парсинге выписок"""
    xmlstr = ElementTree.tostring(treeroot).decode()
    xmlstr = re.sub(r'ns\d:', '', xmlstr)
    xmlstr = re.sub(r':ns\d:', '', xmlstr)
    return ElementTree.fromstring(xmlstr)


def get_date(extract_path):
    try:
        treeroot = fix_ns(ElementTree.parse(extract_path).getroot())

        target = list(treeroot.iter('Sender'))
        if target:
            date = target[0].get('Date_Upload')
            if date:
                return date[:10]
        target = list(treeroot.iter('DeclarAttribute'))
        if target:
            date = target[0].get('ExtractDate')
            if isinstance(date, str):
                date = '-'.join(reversed(date.split('.')))
                return date[:10]
        target = treeroot.find('./details_statement/group_top_requisites/date_formation')
        if target is not None and target.text:
            return target.text[:10]

        return '0000-00-00'
    except Exception as ex:
        print(f'Ошибка получения даты\n\t{extract_path}\n\t{ex}')
        return '0000-00-00'


if __name__ == '__main__':
    filename = '/home/don_durito/TMP/23-02-1104040-3_ПРМ_(c)Субъект РФ-КК.xml'

    print(get_date(filename))