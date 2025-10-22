from tradingview_ta import TA_Handler, Interval, Exchange, TradingView

def main():
    btc = TA_Handler(
        symbol='BTCUSDT.P',
        exchange='binance',
        screener='crypto',
        interval=Interval.INTERVAL_15_MINUTES,
        proxies={'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}
    )
    btc.add_indicators([

    ])
    btc_analysis = btc.get_analysis()
    print(btc_analysis.indicators['low'], btc_analysis.indicators['high'], btc_analysis.indicators['close'])
    print(btc_analysis.indicators)
    print(btc_analysis.oscillators)
    print(btc_analysis.moving_averages)
    print(btc_analysis.time)
    print(btc_analysis.summary)



if __name__ == '__main__':
    main()