"""Adaptadores gratuitos de proventos publicados pelos próprios emissores."""
from datetime import date, datetime
from io import BytesIO
import re
from urllib.request import urlopen
from zipfile import ZipFile

from openpyxl import load_workbook

from .income import decimal_value

ITAU_HISTORY = ('https://api.mziq.com/mzfilemanager/v2/d/'
                '42787847-4cf6-4461-94a5-40ed237dca33/'
                '7a6660b0-44e8-a72b-caf9-013b23915437?origin=2')


def official_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    match = re.fullmatch(r'\s*(\d{2}\.\d{2}\.\d{4})(?:\s*\(\*\*\))?\s*', str(value))
    if not match:
        raise ValueError('Data inválida no histórico oficial.')
    return datetime.strptime(match[1], '%d.%m.%Y').date()


def parse_itau(content, year):
    # Limites também para o conteúdo descompactado do XLSX remoto.
    with ZipFile(BytesIO(content)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 30_000_000:
            raise ValueError('Histórico oficial excede o tamanho permitido.')
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    result = []
    try:
        for sheet in workbook:
            rows = list(sheet.values)
            if len(rows) < 4 or rows[1][:2] != ('Ano', 'Competência do Exercício'):
                raise ValueError('Formato do histórico oficial mudou; consulta cancelada.')
            header = [str(v or '').replace('\n', ' ').strip() for v in rows[1]]
            modern = 'Posição Acionária Brasil' in header
            expected = {2: 'Posição Acionária Brasil' if modern else 'Posição Acionária',
                        5 if modern else 3: 'Data do Pagamento Brasil' if modern else 'Data do Pagamento',
                        7 if modern else 4: 'Tipo de evento'}
            if any(header[i] != name for i, name in expected.items()):
                raise ValueError('Colunas do histórico oficial mudaram.')
            gross = 8 if modern else 5
            if rows[2][gross] != 'Bruto':
                raise ValueError('Coluna de valor bruto não identificada.')
            for row in rows[3:]:
                if not row[1]:  # títulos, rodapés e linhas vazias
                    continue
                pay = official_date(row[5 if modern else 3])
                if pay.year != year:
                    continue
                record = official_date(row[2])
                label = str(row[7 if modern else 4])
                if label.startswith('JCP'):
                    label = 'JCP'
                elif 'Dividendo' in label:
                    label = 'DIVIDENDO'
                else:
                    raise ValueError('Tipo de evento desconhecido no histórico oficial.')
                if record > pay:
                    raise ValueError('Datas inconsistentes no histórico oficial.')
                result.append(dict(paymentDate=pay, lastDatePrior=record,
                    rawRate=decimal_value(row[gross], True), label=label,
                    verified=True, source=ITAU_HISTORY))
    finally:
        workbook.close()
    if not result:
        raise ValueError('Sem cobertura confirmada para este ano no arquivo oficial; não equivale a zero proventos.')
    return result


class OfficialIncomeProvider:
    """Cache somente durante uma consulta anual, compartilhado por ITUB3/ITUB4."""
    def __init__(self):
        self._content = None

    def fetch(self, ticker, kind, year):
        if ticker not in ('ITUB3', 'ITUB4') or kind != 'Ações':
            raise ValueError('Fonte gratuita ainda sem cobertura validada para este ativo. '
                             'Disponível: ITUB3/ITUB4. FIIs e demais ativos não são considerados zerados.')
        if self._content is None:
            try:
                with urlopen(ITAU_HISTORY, timeout=25) as response:
                    content = response.read(5_000_001)
                if len(content) > 5_000_000:
                    raise ValueError('Arquivo muito grande.')
                self._content = content
            except (OSError, ValueError):
                raise ValueError('Não foi possível obter o histórico oficial do Itaú. Tente novamente mais tarde.') from None
        try:
            return parse_itau(self._content, year)
        except ValueError:
            raise
        except Exception:
            raise ValueError('Arquivo oficial inválido ou alterado; dados anteriores devem ser preservados.') from None
