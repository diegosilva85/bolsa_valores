from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from dataclasses import replace
from threading import Lock
from time import monotonic
import math

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    name: str
    timestamps: list[datetime]
    prices: list[float]
    last_price: float
    change: float
    change_percent: float


@dataclass(frozen=True)
class HistoryRange:
    period: str
    interval: str
    limit_days: int | None = None


HISTORY_RANGES: dict[str, HistoryRange] = {
    "Hoje": HistoryRange("1d", "1m"),
    "Última semana": HistoryRange("5d", "5m"),
    "Últimos 15 dias": HistoryRange("1mo", "30m", 15),
    "Último mês": HistoryRange("1mo", "30m"),
    "Último trimestre": HistoryRange("3mo", "1d"),
    "Último semestre": HistoryRange("6mo", "1d"),
    "Ano atual": HistoryRange("ytd", "1d"),
    "Último ano": HistoryRange("1y", "1d"),
    "2 anos": HistoryRange("2y", "1d"),
    "5 anos": HistoryRange("5y", "1wk"),
}


class YahooFinanceProvider:
    """Fonte inicial de cotações. Dados podem ter atraso e não são oficiais da B3."""

    def __init__(self):
        self._fx_lock = Lock()
        self._fx = None

    def usd_brl(self):
        with self._fx_lock:
            if self._fx and monotonic() - self._fx[0] < 60:
                return self._fx[1:]
            frame = yf.Ticker('BRL=X').history(period='5d', interval='5m', timeout=15)
            close = frame['Close'].dropna()
            if close.empty or not math.isfinite(float(close.iloc[-1])) or close.iloc[-1] <= 0:
                raise ValueError('Cotação USD/BRL indisponível.')
            self._fx = (monotonic(), float(close.iloc[-1]), close.index[-1].to_pydatetime())
            return self._fx[1:]


    @staticmethod
    def converted(snapshot, rate):
        return replace(snapshot, prices=[p * rate for p in snapshot.prices],
                       last_price=snapshot.last_price * rate, change=snapshot.change * rate)

    def history(
        self,
        range_name: str = "Hoje",
        symbol: str = "^BVSP",
        name: str = "Ibovespa",
    ) -> MarketSnapshot:
        try:
            selected_range = HISTORY_RANGES[range_name]
        except KeyError as exc:
            raise ValueError(f"Período desconhecido: {range_name}") from exc

        ticker = yf.Ticker(symbol)
        frame = ticker.history(
            period=selected_range.period,
            interval=selected_range.interval,
            auto_adjust=False,
            prepost=False,
            timeout=15,
        )
        if frame.empty and range_name == "Hoje":
            # Fora do pregão, alguns instrumentos não retornam candles no período de 1 dia.
            frame = ticker.history(
                period="5d",
                interval="5m",
                auto_adjust=False,
                prepost=False,
                timeout=15,
            )
        if frame.empty:
            raise RuntimeError("O provedor não retornou cotações para o ativo.")

        close = frame["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.dropna().astype(float)
        close = close.sort_index()
        close = close.loc[~close.index.duplicated(keep='last')]
        if close.index.tz is not None:
            close.index = close.index.tz_convert('America/Sao_Paulo')
        else:
            close.index = close.index.tz_localize('America/Sao_Paulo')
        if range_name == 'Hoje' and not close.empty:
            close = close.loc[close.index.date == close.index[-1].date()]
        if selected_range.limit_days and not close.empty:
            cutoff = close.index[-1] - pd.Timedelta(days=selected_range.limit_days)
            close = close.loc[close.index >= cutoff]
        if close.empty:
            raise RuntimeError("A resposta não contém preços válidos.")

        first = float(close.iloc[0])
        last = float(close.iloc[-1])
        change = last - first
        change_percent = (change / first * 100.0) if first else 0.0

        timestamps = [item.to_pydatetime() for item in close.index]
        return MarketSnapshot(
            symbol=symbol,
            name=name,
            timestamps=timestamps,
            prices=close.tolist(),
            last_price=last,
            change=change,
            change_percent=change_percent,
        )

    def intraday(self, symbol: str = "^BVSP", name: str = "Ibovespa") -> MarketSnapshot:
        """Compatibilidade com a primeira versão do aplicativo."""
        return self.history("Hoje", symbol, name)
