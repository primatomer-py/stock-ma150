import streamlit as st
import yfinance as yf

WINDOW = 150

st.set_page_config(page_title="בדיקת ממוצע 150", page_icon="📈")

# כיוון ימין לשמאל
st.markdown(
    "<style>.stApp {direction: rtl; text-align: right;}</style>",
    unsafe_allow_html=True,
)

st.title("📈 האם המניה מעל או מתחת לממוצע 150?")
st.write("הקלד סימול מניה (למשל AAPL, או TEVA.TA למניה ישראלית).")

ticker = st.text_input("סימול מניה").strip().upper()

if ticker:
    try:
        data = yf.Ticker(ticker).history(period="2y")["Close"].dropna()
    except Exception as e:
        st.error(f"שגיאה בשליפת הנתונים: {e}")
        st.stop()

    if len(data) < WINDOW:
        st.warning(f"אין מספיק נתונים עבור {ticker} (נמצאו {len(data)} ימים).")
        st.stop()

    ma = data.rolling(WINDOW).mean()
    price = float(data.iloc[-1])
    avg = float(ma.iloc[-1])
    diff = (price - avg) / avg * 100

    if price > avg:
        st.success(f"{ticker} נסחרת **מעל** הממוצע ב-{abs(diff):.1f}%")
    else:
        st.error(f"{ticker} נסחרת **מתחת** לממוצע ב-{abs(diff):.1f}%")

    c1, c2 = st.columns(2)
    c1.metric("מחיר אחרון", f"{price:,.2f}")
    c2.metric(f"ממוצע {WINDOW} יום", f"{avg:,.2f}")

    st.line_chart({"מחיר": data, f"ממוצע {WINDOW}": ma})

st.caption("כלי מידע בלבד, לא המלצה להשקעה.")
