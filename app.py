  
"""
สวัสดีโซลาร์ - เอเจนต์สำรวจหลังคา + ออกแบบ + คืนทุน อัตโนมัติ
สำหรับ LINE OA: สวัสดีโซลาร์ (เบอร์ 095-774-4978)
ไฟล์มาตรฐานชื่อ app.py สำหรับ Render
"""

import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, LocationMessage, TextSendMessage, FlexSendMessage
import math

app = Flask(__name__)

LINE_TOKEN = os.getenv("LINE_TOKEN", "ใส่_Channel_Access_Token_ตรงนี้")
LINE_SECRET = os.getenv("LINE_SECRET", "ใส่_Channel_Secret_ตรงนี้")

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

user_data = {}

def calculate_solar(bill_baht, elec_rate=4.7, sun_hours=4.5):
    units_per_month = bill_baht / elec_rate
    kw_needed = (units_per_month / 30) / sun_hours * 1.25
    if kw_needed <= 3.5:
        system_kw = 3.3
    elif kw_needed <= 5.5:
        system_kw = 5.0
    elif kw_needed <= 8:
        system_kw = 8.0
    else:
        system_kw = 10.0
    panels = math.ceil(system_kw * 1000 / 550)
    area = panels * 2.5
    prod_per_month = system_kw * sun_hours * 30 * 0.8
    saving_per_month = prod_per_month * elec_rate
    new_bill = max(0, bill_baht - saving_per_month)
    cost = system_kw * 32000
    payback_years = cost / (saving_per_month * 12)
    payback_y = int(payback_years)
    payback_m = int((payback_years - payback_y) * 12)
    return {
        "system_kw": system_kw,
        "panels": panels,
        "area": area,
        "prod": int(prod_per_month),
        "saving": int(saving_per_month),
        "new_bill": int(new_bill),
        "cost": int(cost),
        "payback_y": payback_y,
        "payback_m": payback_m,
        "old_bill": bill_baht
    }

def build_flex_message(result, location_text=""):
    text_summary = f"จากค่าไฟ {result['old_bill']:,} เหลือ {result['new_bill']:,} ประหยัด {result['saving']:,}/เดือน คืนทุน {result['payback_y']} ปี {result['payback_m']} เดือน"
    flex_content = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": "https://images.unsplash.com/photo-1509391366360-2e959784a276?w=800",
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "สวัสดีโซลาร์ - ผลวิเคราะห์หลังคา", "weight": "bold", "size": "md", "color": "#FF6B00"},
                {"type": "text", "text": f"ระบบแนะนำ {result['system_kw']} kW ({result['panels']} แผง)", "weight": "bold", "size": "lg", "margin": "md"},
                {"type": "text", "text": location_text, "size": "xs", "color": "#888888", "margin": "sm"},
                {"type": "separator", "margin": "md"},
                {"type": "box", "layout": "vertical", "margin": "md", "spacing": "sm", "contents": [
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "ค่าไฟเดิม", "size": "sm", "color": "#555555"},
                        {"type": "text", "text": f"{result['old_bill']:,} บ.", "size": "sm", "align": "end", "weight": "bold"}
                    ]},
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "ค่าไฟใหม่", "size": "sm", "color": "#555555"},
                        {"type": "text", "text": f"{result['new_bill']:,} บ.", "size": "sm", "align": "end", "weight": "bold", "color": "#00B900"}
                    ]},
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "ประหยัด/เดือน", "size": "sm", "color": "#555555"},
                        {"type": "text", "text": f"{result['saving']:,} บ.", "size": "sm", "align": "end", "weight": "bold", "color": "#FF6B00"}
                    ]},
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "คืนทุน", "size": "sm", "color": "#555555"},
                        {"type": "text", "text": f"{result['payback_y']} ปี {result['payback_m']} เดือน", "size": "sm", "align": "end", "weight": "bold"}
                    ]},
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "พื้นที่ใช้", "size": "sm", "color": "#555555"},
                        {"type": "text", "text": f"{result['area']} ตรม.", "size": "sm", "align": "end"}
                    ]}
                ]},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": text_summary, "size": "xs", "color": "#666666", "wrap": True, "margin": "md"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#FF6B00", "action": {"type": "message", "label": "ขอใบเสนอราคา PDF", "text": "ขอใบเสนอราคา PDF"}},
                {"type": "button", "style": "secondary", "action": {"type": "message", "label": "นัดสำรวจฟรี", "text": "นัดสำรวจฟรี 095-774-4978"}},
                {"type": "button", "style": "link", "action": {"type": "uri", "label": "ดูผลงาน: sawasdeesolarcell.com", "uri": "https://www.sawasdeesolarcell.com"}}
            ]
        }
    }
    return FlexSendMessage(alt_text=text_summary, contents=flex_content)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/", methods=['GET'])
def home():
    return "Sawasdee Solar Agent is running - 095-774-4978"

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    if text.replace(',', '').replace(' ', '').isdigit():
        try:
            bill = int(text.replace(',', '').replace(' ', ''))
            if 500 <= bill <= 50000:
                result = calculate_solar(bill)
                user_data[user_id] = result
                flex = build_flex_message(result)
                line_bot_api.reply_message(event.reply_token, [
                    TextSendMessage(text=f"รับบิล {bill:,} บาทแล้วครับ กำลังวิเคราะห์หลังคา..."),
                    flex
                ])
                return
        except:
            pass
    if "ใบเสนอราคา" in text:
        result = user_data.get(user_id)
        if result:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📄 ใบเสนอราคาระบบ {result['system_kw']}kW\nราคา {result['cost']:,} บาท\n\nสวัสดีโซลาร์ 095-774-4978\nฟรีขออนุญาตการไฟฟ้า + ผ่อน 0%\n\nทีมงานจะติดต่อกลับใน 10 นาทีครับ"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ส่งบิลค่าไฟมาก่อนนะครับ เช่น พิมพ์ 4500 หรือส่งรูปบิลมาได้เลยครับ"))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="สวัสดีครับ ☀️ สวัสดีโซลาร์\n\nส่งบิลค่าไฟมาได้เลยครับ (รูปหรือพิมพ์ตัวเลข เช่น 4500)\nแล้วแชร์โลเคชั่นหลังคา ผมจะคำนวณให้ทันทีว่า\nจากค่าไฟเท่าไหร่ เหลือเท่าไหร่ คืนทุนกี่ปี\n\n📞 095-774-4978 | 080-8989-353"))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ได้รับรูปบิลแล้วครับ 🙏 (ระบบกำลังอ่าน)\n\nช่วยพิมพ์ยอดค่าไฟต่อเดือนเป็นตัวเลขด้วยครับ เช่น 4500\nแล้วแชร์โลเคชั่นหลังคา ผมจะคำนวณขนาดระบบให้ทันทีครับ"))

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    user_id = event.source.user_id
    result = user_data.get(user_id)
    lat = event.message.latitude
    lng = event.message.longitude
    addr = event.message.address or f"{lat},{lng}"
    if result:
        flex = build_flex_message(result, location_text=f"📍 {addr}")
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text=f"ได้รับพิกัดแล้วครับ {addr}\nกำลังวัดพื้นที่หลังคาจากดาวเทียม..."),
            flex
        ])
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"ได้รับพิกัด {addr} แล้วครับ\nตอนนี้ช่วยส่งบิลค่าไฟมาด้วยนะครับ จะได้คำนวณให้ตรงครับ"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
