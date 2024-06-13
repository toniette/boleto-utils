import re
import pytz
import json
from datetime import datetime, timedelta


class Bank:
    COMPE: str
    ISPB: str
    Document: str
    LongName: str
    ShortName: str
    Network: str
    Type: str
    PixType: str
    Charge: bool
    CreditDocument: bool
    LegalCheque: bool
    DetectaFlow: bool
    PCR: bool
    PCRP: bool
    SalaryPortability: str
    Products: list[str]
    Url: str
    DateOperationStarted: str
    DatePixStarted: str
    DateRegistered: str
    DateUpdated: str

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


########################################################################################################################


class BanksList:
    banks: list[Bank] = []

    def __init__(self, banks_list_file_path: str = 'banks_list.json'):
        file = open(banks_list_file_path, 'r')
        banks = json.loads(file.read())
        self.banks = [Bank(**bank) for bank in banks]
        file.close()

    def __getitem__(self, item):
        return self.banks[item]

    def __iter__(self):
        return iter(self.banks)

    def __len__(self):
        return len(self.banks)

    def filter(self, **kwargs):
        return [bank for bank in self.banks if all([bank.__dict__[key] == value for key, value in kwargs.items()])]

    def first(self, **kwargs):
        return next(iter(self.filter(**kwargs)), None)


########################################################################################################################


class ModService:
    @staticmethod
    def mod_10(number: str) -> str:
        reversed_number = reversed(number)

        factor = 2
        total = 0
        for num in reversed_number:
            result = factor * int(num)
            result = sum([int(d) for d in str(result)])
            total += result
            factor = (factor % 2) + 1

        base = 10
        rest = total % base
        dv = base - rest
        return str(dv)

    @staticmethod
    def mod_11(number: str) -> str:
        reversed_number = reversed(number)

        factor = 2
        total = 0
        for num in reversed_number:
            result = factor * int(num)
            total += result
            factor = (factor % 9) + 1 + (factor // 9) * 1

        base = 11
        rest = total % base
        dv = base - rest
        return str(dv)


########################################################################################################################


class DACService:
    @staticmethod
    def dac_10(number: str, dv_to_dv_mapping=None):
        dv = ModService().mod_10(number)

        try:
            dv = dv_to_dv_mapping[dv]
        except (TypeError, KeyError):
            pass

        return dv

    @staticmethod
    def dac_11(number: str, dv_to_dv_mapping=None):
        dv = ModService().mod_11(number)

        try:
            dv = dv_to_dv_mapping[dv]
        except (TypeError, KeyError):
            pass

        return str(dv)


########################################################################################################################


class BilletService:
    def __init__(self, raw: str):
        self.raw: str | None = raw

        self.unmasked: str | None = None
        self.identifier_type: str | None = None
        self.line: str | None = None
        self.barcode: str | None = None
        self.value: float | None = 0.0
        self.type: str | None = None
        self.bank: str | None = None
        self.due_date: str | None = None
        self.is_guide: bool = False
        self.is_valid: bool = False

        self._parse()

    def _parse(self):
        self._unmasked()
        self._identifier_type()

        if self.identifier_type == 'line':
            self.line = self.unmasked
            self._barcode()
        elif self.identifier_type == 'barcode':
            self.barcode = self.unmasked
            self._line()

        if self.validate():
            self._data()
            return

        self.is_guide = True
        if self.identifier_type == 'line':
            self.line = self.unmasked
            self._guide_barcode()
        elif self.identifier_type == 'barcode':
            self.barcode = self.unmasked
            self._guide_line()

        if self.validate():
            self._data()
            return
        raise ValueError('O identificador informado é inválido.')

    def _data(self):
        self._type()
        self._value()
        self._bank()
        self._due_date()

    def _due_date(self):
        base_date = datetime(1997, 10, 7, tzinfo=pytz.utc)
        if self.type == 'Cartão de crédito' or self.type == 'Bancário':
            rate = int(self.barcode[5:9])
            if rate:
                date = base_date + timedelta(days=rate)
                self.due_date = date.strftime('%Y-%m-%d')
                return self.due_date
        self.due_date = None
        return self.due_date

    def _bank(self):
        bank_code = self.barcode[0:3]
        bank = BanksList().first(COMPE=bank_code)
        if not bank:
            self.bank = None
            return self.bank
        self.bank = bank
        return self.bank

    def _unmasked(self):
        filtered = re.sub(r'\D', '', self.raw)
        if len(filtered) == 46:
            self.raw += '0'
        if len(filtered) == 36:
            self.raw += '0' * 11
        self.unmasked = re.sub(r'\D', '', filtered)
        return self.unmasked

    def validate(self):
        if self.is_guide:
            is_valid = self._guide_validate_line() and self._guide_validate_barcode()
            self.is_valid = is_valid
            return self.is_valid
        self.is_valid = self._validate_line() and self._validate_barcode()
        return self.is_valid

    def _identifier_type(self):
        if len(self.unmasked) in [47, 48]:
            self.identifier_type = 'line'
            return self.identifier_type
        elif len(self.unmasked) == 44:
            self.identifier_type = 'barcode'
            return self.identifier_type
        else:
            raise ValueError('O identificador informado é inválido.')

    def _type(self):
        self.type = None
        if self.line[-14:] == '00000000000000' or self.line[5:19] == '00000000000000':
            self.type = 'Cartão de crédito'
        elif self.line[0] == '8':
            if self.line[1] == '1':
                self.type = 'Arrecadação de tributo'
            elif self.line[1] == '2':
                self.type = 'Saneamento'
            elif self.line[1] == '3':
                self.type = 'Gás e energia'
            elif self.line[1] == '4':
                self.type = 'Telecomunicação'
            elif self.line[1] == '5':
                self.type = 'Arrecadação governamental'
            elif self.line[1] in ['6', '9']:
                self.type = 'Desconhecido'
            elif self.line[1] == '7':
                self.type = 'Taxa de trânsito'
        else:
            self.type = 'Bancário'
        return self.type

    def _validate_line(self):
        part_1 = self.line[0:9]
        dv_1 = self.line[9]
        calculated_dv_1 = self.get_line_dv(part_1)
        is_dv_1_correct = dv_1 == calculated_dv_1

        part_2 = self.line[10:20]
        dv_2 = self.line[20]
        calculated_dv_2 = self.get_line_dv(part_2)
        is_dv_2_correct = dv_2 == calculated_dv_2

        part_3 = self.line[21:31]
        dv_3 = self.line[31]
        calculated_dv_3 = self.get_line_dv(part_3)
        is_dv_3_correct = dv_3 == calculated_dv_3

        return is_dv_1_correct and is_dv_2_correct and is_dv_3_correct

    def _get_barcode_dv(self) -> str:
        number = self.barcode[:4] + self.barcode[5:]
        return DACService().dac_11(number, dv_to_dv_mapping={'11': '1', '10': '1'})

    def _validate_barcode(self):
        dv = self.barcode[4]
        calculated_dv = self._get_barcode_dv()
        return dv == calculated_dv

    def _line(self) -> str:
        part_1 = self.barcode[0:4] + self.barcode[19:24]
        dv_1 = self.get_line_dv(part_1)

        part_2 = self.barcode[24:34]
        dv_2 = self.get_line_dv(part_2)

        part_3 = self.barcode[34:44]
        dv_3 = self.get_line_dv(part_3)

        part_4 = self.barcode[4]
        part_5 = self.barcode[5:19]

        self.line = f'{part_1}{dv_1}{part_2}{dv_2}{part_3}{dv_3}{part_4}{part_5}'
        return self.line

    def _barcode(self) -> str:
        part_1 = self.line[0:4]
        part_2 = self.line[32:47]
        part_3 = self.line[4:9]
        part_4 = self.line[10:20]
        part_5 = self.line[21:31]
        self.barcode = f'{part_1}{part_2}{part_3}{part_4}{part_5}'
        return self.barcode

    def _guide_validate_line(self):
        method_to_calculate_dv = self._get_dv_method_for_barcode_or_line(self.barcode)

        part_1 = self.line[0:11]
        dv_1 = self.line[11]
        calculated_dv_1 = method_to_calculate_dv(part_1)
        is_dv_1_correct = dv_1 == calculated_dv_1

        part_2 = self.line[12:23]
        dv_2 = self.line[23]
        calculated_dv_2 = method_to_calculate_dv(part_2)
        is_dv_2_correct = dv_2 == calculated_dv_2

        part_3 = self.line[24:35]
        dv_3 = self.line[35]
        calculated_dv_3 = method_to_calculate_dv(part_3)
        is_dv_3_correct = dv_3 == calculated_dv_3

        part_4 = self.line[36:47]
        dv_4 = self.line[47]
        calculated_dv_4 = method_to_calculate_dv(part_4)
        is_dv_4_correct = dv_4 == calculated_dv_4

        return is_dv_1_correct and is_dv_2_correct and is_dv_3_correct and is_dv_4_correct

    def _guide_validate_barcode(self):
        dv = self.barcode[3]
        method_to_calculate_dv = self._get_dv_method_for_barcode_or_line(self.barcode)
        calculated_dv = method_to_calculate_dv(self.barcode)

        return dv == calculated_dv

    def _calculate_dv_10(self, barcode_or_line: str) -> str:
        if len(barcode_or_line) == 44:
            number = self._get_number_from_barcode_or_line(barcode_or_line)
        else:
            number = barcode_or_line

        return DACService().dac_10(number, dv_to_dv_mapping={'10': '0'})

    def _calculate_dv_11(self, barcode_or_line: str) -> str:
        if len(barcode_or_line) == 44:
            number = self._get_number_from_barcode_or_line(barcode_or_line)
        else:
            number = barcode_or_line

        return DACService().dac_11(number, dv_to_dv_mapping={'10': '0', '11': '0'})

    def _get_dv_method_for_barcode_or_line(
            self, barcode_or_line: str
    ) -> callable:
        reference = barcode_or_line[2]
        mapping_to_dv_method = {
            '6': self._calculate_dv_10,
            '7': self._calculate_dv_10,
            '8': self._calculate_dv_11,
            '9': self._calculate_dv_11,
        }
        try:
            method_to_calculate_dv = mapping_to_dv_method[reference]
        except KeyError as e:
            raise ValueError('Valor real ou referência inválida!') from e
        return method_to_calculate_dv

    def _guide_line(self) -> str:
        method_to_calculate_dv = self._get_dv_method_for_barcode_or_line(self.barcode)

        part_1 = self.barcode[0:11]
        dv_1 = method_to_calculate_dv(part_1)

        part_2 = self.barcode[11:22]
        dv_2 = method_to_calculate_dv(part_2)

        part_3 = self.barcode[22:33]
        dv_3 = method_to_calculate_dv(part_3)

        part_4 = self.barcode[33:44]
        dv_4 = method_to_calculate_dv(part_4)

        self.line = f'{part_1}{dv_1}{part_2}{dv_2}{part_3}{dv_3}{part_4}{dv_4}'
        return self.line

    def _guide_barcode(self) -> str:
        part_1 = self.line[0:11]
        part_2 = self.line[12:23]
        part_3 = self.line[24:35]
        part_4 = self.line[36:47]
        self.barcode = f'{part_1}{part_2}{part_3}{part_4}'
        return self.barcode

    def _value(self):
        if self.is_guide:
            self.value = self._get_guide_value()
            return self.value
        self.value = self._get_billet_value()
        return self.value

    def _get_billet_value(self):
        return int(self.barcode[9:19]) / 100

    def _get_guide_value(self):
        return int(self.barcode[4:15]) / 100

    @staticmethod
    def _get_number_from_barcode_or_line(barcode_or_line: str) -> str:
        return barcode_or_line[:3] + barcode_or_line[4:]

    @staticmethod
    def get_line_dv(partial) -> str:
        return DACService().dac_10(partial, dv_to_dv_mapping={'10': '0'})
