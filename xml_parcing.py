from xml.etree import ElementTree
import re


def fix_ns(treeroot):
    """Удаляем паразитные неймспейсы, которые какой-то причине порождаются ElementTree при парсинге выписок"""
    xmlstr = ElementTree.tostring(treeroot).decode()
    xmlstr = re.sub(r'ns\d:', '', xmlstr)
    xmlstr = re.sub(r':ns\d:', '', xmlstr)
    return ElementTree.fromstring(xmlstr)


def check_cession(extract_path):
    """Выявляем выписки, в которых один собственник продал участок другому в тот же день, когда участок был передан ему
     в собственность. Делаем это путем поиска одинаковых дат регистрации собственности"""
    treeroot = fix_ns(ElementTree.parse(extract_path).getroot())
    reg_dates = [d.text.strip() for d in treeroot.iter('RegDate')]
    if len(reg_dates) > len(set(reg_dates)):
        return True
    return False


test_path = '/home/don_durito/downloads/Telegram Desktop/23_33_1201009_6_#_Тахтаджян_Е_Андрониковна+Григорьева_В_Н_+Прокофьев.xml'
test_path_f = '/home/don_durito/downloads/Telegram Desktop/23_30_0903020_497_ЗНП_Сквер_cСтаротитаровское_СП_Темрюкский_р_н.xml'
if __name__ == '__main__':
    print(check_cession(test_path_f))
