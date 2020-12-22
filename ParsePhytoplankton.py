from docx2python import docx2python
from enum import Enum
import csv

class PhytoplanktonEnum(Enum):
    """Перечисление для отслеживания таблицы, которая парсится в данный момент"""
    header = 1
    body = 2
    bottom = 3
    notGood = 4

class HeaderModel:
    """Модель для хранения свойств заголовка таблицы"""
    def __init__(self, water="", date="", station="", depth="", temperature="", alpha="", author=""):
        self.water = water
        self.date = date
        self.station = station
        self.depth = depth #глубина
        self.temperature = temperature
        self.alpha = alpha
        self.author = author

class TaksonOrDepartmentModel:
    """Модель для хранения свойств таблиц: Отдел и Таксон"""
    def __init__(self, takson, counter, bioMassa, percentCounter, percentBioMassa):
        self.takson = takson
        self.counter = counter
        self.bioMassa = bioMassa
        self.percentCounter = percentCounter
        self.percentBioMassa = percentBioMassa

class PhytoplanktonModel:
    """Модель для ханения данных одной полной таблице о фитопланктоне"""
    def __init__(self, head, body, bottom):
        self.head = head
        self.body = body
        self.bottom = bottom

class ParsePhytoplankton:
    """Класс для парсинга данных о фитопланктоне"""

    def __init__(self, path):
        """ path - путь к файлу с исходными данными """
        self.path = path
        self.parseData = []
        self.parseState = PhytoplanktonEnum.notGood
        self.isStart = True

        try:
            self.doc_result = docx2python(path)
        except:
            print("Файл не найден")
            self.isStart = False

        if self.isStart:
            self.startParse()

    def headerParse(self, content, header):
        """Метод для парсинг заголовка таблицы"""
        if "Водоем:" in content:
            frst = content.find("Дата")
            scnd = content.find("Станция")
            header.water = content[7:frst].strip()
            header.date = content[frst + 5:scnd].strip()
            header.station = content[scnd + 8:].strip()
        elif "Глубина:" in content:
            frst = content.find("Температура")
            scnd = content.find("Прозрачность")
            header.depth = content[8:frst].strip()
            header.temperature = content[frst + 12:scnd].strip()
            header.alpha = content[scnd + 13:].strip()
        elif "Исполнитель:" in content:
            header.author = content[12:].strip()

    def taksonOrDepartmentParse(self, content):
        """Метод для парсинг таблиц: Отдел и Таксон"""
        if content[0][0] != "Отдел" and content[0][0] != "Таксон":
            return TaksonOrDepartmentModel(content[0][0], content[1][0], content[2][0], content[3][0], content[4][0])
        return 0

    def saveData(self):
        """
            Метод для сохранения данных в файлы:
                      headerPhytoplankton.tsv,
                      bodyPhytoplankton.tsv,
                      bottomPhytoplankton.tsv
        """
        with open('headerPhytoplankton.tsv', 'wt') as out_file:
            tsv_writer = csv.writer(out_file, delimiter='\t')
            counter = 0
            for i in self.parseData:
                tsv_writer.writerow(
                    [counter, i.head.water, i.head.date, i.head.station, i.head.depth, i.head.temperature, i.head.alpha,
                     i.head.author])
                counter += 1

        with open('bodyPhytoplankton.tsv', 'wt') as out_file:
            tsv_writer = csv.writer(out_file, delimiter='\t')
            counter = 0
            for i in self.parseData:
                for j in i.body:
                    tsv_writer.writerow([counter, j.takson, j.counter, j.bioMassa, j.percentCounter, j.percentBioMassa])
                counter += 1

        with open('bottomPhytoplankton.tsv', 'wt') as out_file:
            tsv_writer = csv.writer(out_file, delimiter='\t')
            counter = 0
            for i in self.parseData:
                for j in i.bottom:
                    tsv_writer.writerow([counter, j.takson, j.counter, j.bioMassa, j.percentCounter, j.percentBioMassa])
                counter += 1

    def startParse(self):
        """Главный метод для парсинга"""
        for j in self.doc_result.body:
            header = HeaderModel()
            bottom = []
            body = []

            for i in j:
                if i[0][0] == "":
                    continue

                if "Водоем:" in i[0][0]:
                    self.parseState = PhytoplanktonEnum.header
                elif "Таксон" == i[0][0]:
                    self.parseState = PhytoplanktonEnum.body
                elif "Отдел" == i[0][0]:
                    self.parseState = PhytoplanktonEnum.bottom
                elif "Всего" == i[0][0]:
                    takson = self.taksonOrDepartmentParse(i)
                    if takson != 0:
                        bottom.append(takson)
                    self.parseState = PhytoplanktonEnum.notGood

                if self.parseState == PhytoplanktonEnum.header:
                    self.headerParse(i[0][0], header)
                elif self.parseState == PhytoplanktonEnum.body or self.parseState == PhytoplanktonEnum.bottom:
                    takson = self.taksonOrDepartmentParse(i)
                    if takson != 0 and self.parseState == PhytoplanktonEnum.body:
                        body.append(takson)
                    elif takson != 0 and self.parseState == PhytoplanktonEnum.bottom:
                        bottom.append(takson)

            if header.author != "":
                self.parseData.append(PhytoplanktonModel(header, body, bottom))

            self.saveData()