"""
สวัสดีโซลาร์ - V3 Fixed Flex ไม่มีข้อความว่าง
"""
import os, math, hmac, hashlib, base64, traceback, requests, json
from flask import Flask, request, abort

app = Flask(__name__)
LINE_TOKEN = os.getenv("LINE_TOKEN","").strip()
LINE_SECRET = os.getenv("LINE_SECRET","").strip()
print(f"=== Sawasdee Solar Agent V3 Starting ===")
print(f"TOKEN len: {len(LINE_TOKEN)} SECRET len: {len(LINE_SECRET)}")
user_data={}

def calculate_solar(bill_baht, elec_rate=4.7, sun_hours=4.5):
    units_per_month=bill_baht/elec_rate
    kw_needed=(units_per_month/30)/sun_hours*1.25
    if kw_needed<=3.5: system_kw=3.3
    elif kw_needed<=5.5: system_kw=5.0
    elif kw_needed<=8: system_kw=8.0
    else: system_kw=10.0
    panels=math.ceil(system_kw*1000/550)
    area=panels*2.5
    prod_per_month=system_kw*sun_hours*30*0.8
    saving_per_month=prod_per_month*elec_rate
    new_bill=max(0,bill_baht-saving_per_month)
    cost=system_kw*32000
    payback_years=cost/(saving_per_month*12)
    payback_y=int(payback_years)
    payback_m=int((payback_years-payback_y)*12)
    return {"system_kw":system_kw,"panels":panels,"area":area,"prod":int(prod_per_month),"saving":int(saving_per_month),"new_bill":int(new_bill),"cost":int(cost),"payback_y":payback_y,"payback_m":payback_m,"old_bill":bill_baht}

def build_flex_json(result, location_text=""):
    # สร้าง body contents แบบไม่ให้มี text ว่าง
    body_contents=[
        {"type":"text","text":"สวัสดีโซลาร์ - ผลวิเคราะห์หลังคา","weight":"bold","size":"md","color":"#FF6B00"},
        {"type":"text","text":f"ระบบแนะนำ {result['system_kw']} kW ({result['panels']} แผง)","weight":"bold","size":"lg","margin":"md"},
    ]
    if location_text and str(location_text).strip() != "":
        body_contents.append({"type":"text","text":str(location_text)[:200],"size":"xs","color":"#888888","margin":"sm","wrap":True})
    body_contents.append({"type":"separator","margin":"md"})
    body_contents.append({
        "type":"box","layout":"vertical","margin":"md","spacing":"sm","contents":[
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"ค่าไฟเดิม","size":"sm","color":"#555555"},{"type":"text","text":f"{result['old_bill']:,} บ.","size":"sm","align":"end","weight":"bold"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"ค่าไฟใหม่","size":"sm","color":"#555555"},{"type":"text","text":f"{result['new_bill']:,} บ.","size":"sm","align":"end","weight":"bold","color":"#00B900"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"ประหยัด/เดือน","size":"sm","color":"#555555"},{"type":"text","text":f"{result['saving']:,} บ.","size":"sm","align":"end","weight":"bold","color":"#FF6B00"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"คืนทุน","size":"sm","color":"#555555"},{"type":"text","text":f"{result['payback_y']} ปี {result['payback_m']} เดือน","size":"sm","align":"end","weight":"bold"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"พื้นที่ใช้","size":"sm","color":"#555555"},{"type":"text","text":f"{result['area']} ตรม.","size":"sm","align":"end"}]}
        ]
    })
    body_contents.append({"type":"separator","margin":"md"})
    body_contents.append({"type":"text","text":f"จากค่าไฟ {result['old_bill']:,} เหลือ {result['new_bill']:,} ประหยัด {result['saving']:,}/เดือน คืนทุน {result['payback_y']} ปี {result['payback_m']} เดือน","size":"xs","color":"#666666","wrap":True,"margin":"md"})

    flex_content={
        "type":"bubble",
        "hero":{"type":"image","url":"https://images.unsplash.com/photo-1509391366360-2e959784a276?w=800","size":"full","aspectRatio":"20:13","aspectMode":"cover"},
        "body":{"type":"box","layout":"vertical","contents":body_contents},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#FF6B00","action":{"type":"message","label":"ขอใบเสนอราคา PDF","text":"ขอใบเสนอราคา PDF"}},
            {"type":"button","style":"secondary","action":{"type":"message","label":"นัดสำรวจฟรี","text":"นัดสำรวจฟรี 095-774-4978"}},
            {"type":"button","style":"link","action":{"type":"uri","label":"ดูผลงาน: sawasdeesolarcell.com","uri":"https://www.sawasdeesolarcell.com"}}
        ]}
    }
    return flex_content

def verify_signature(body, signature):
    if not LINE_SECRET: return True
    hash=hmac.new(LINE_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    expected=base64.b64encode(hash).decode('utf-8')
    return hmac.compare_digest(signature, expected)

def reply_message(reply_token, messages):
    if not LINE_TOKEN: 
        print("No LINE_TOKEN"); return
    url="https://api.line.me/v2/bot/message/reply"
    headers={"Content-Type":"application/json","Authorization":f"Bearer {LINE_TOKEN}"}
    data={"replyToken":reply_token,"messages":messages}
    try:
        print(f"Replying {reply_token[:10]}... {len(messages)} msgs")
        resp=requests.post(url, headers=headers, json=data, timeout=10)
        print(f"LINE API: {resp.status_code} {resp.text[:800]}")
    except Exception as e:
        print(f"Reply error {e}"); traceback.print_exc()

@app.route("/callback", methods=['POST'])
def callback():
    signature=request.headers.get('X-Line-Signature','')
    body=request.get_data(as_text=True)
    print(f"Webhook received: {body[:600]}")
    if LINE_SECRET and not verify_signature(body, signature):
        print("Invalid signature"); abort(400)
    try:
        data=json.loads(body)
        for event in data.get('events',[]):
            reply_token=event.get('replyToken')
            user_id=event.get('source',{}).get('userId','unknown')
            if event.get('type')=='message':
                msg=event.get('message',{})
                mtype=msg.get('type')
                if mtype=='text':
                    text=msg.get('text','').strip()
                    print(f"Text from {user_id}: {text}")
                    handle_text(reply_token,user_id,text)
                elif mtype=='image':
                    reply_message(reply_token,[{"type":"text","text":"ได้รับรูปบิลแล้วครับ 🙏 พิมพ์ยอดค่าไฟ เช่น 4500 แล้วแชร์โลเคชั่นได้เลยครับ"}])
                elif mtype=='location':
                    addr=msg.get('address',f"{msg.get('latitude')},{msg.get('longitude')}")
                    handle_location(reply_token,user_id,addr)
    except Exception as e:
        print(f"Callback error {e}"); traceback.print_exc()
    return 'OK'

def handle_text(reply_token,user_id,text):
    cleaned=text.replace(',','').replace(' ','')
    if cleaned.isdigit():
        try:
            bill=int(cleaned)
            if 500<=bill<=50000:
                result=calculate_solar(bill)
                user_data[user_id]=result
                flex=build_flex_json(result)
                reply_message(reply_token,[
                    {"type":"text","text":f"รับบิล {bill:,} บาทแล้วครับ กำลังวิเคราะห์..."},
                    {"type":"flex","altText":f"ระบบ {result['system_kw']}kW ประหยัด {result['saving']} บ.","contents":flex}
                ])
                return
        except Exception as e: print(f"Calc error {e}")
    if "ใบเสนอราคา" in text:
        result=user_data.get(user_id)
        if result:
            reply_message(reply_token,[{"type":"text","text":f"📄 ใบเสนอราคาระบบ {result['system_kw']}kW ราคา {result['cost']:,} บาท\nสวัสดีโซลาร์ 095-774-4978"}])
        else:
            reply_message(reply_token,[{"type":"text","text":"ส่งบิลค่าไฟมาก่อนนะครับ เช่น 4500"}])
    else:
        reply_message(reply_token,[{"type":"text","text":"สวัสดีครับ ☀️ สวัสดีโซลาร์\nส่งบิลค่าไฟมาได้เลยครับ (พิมพ์ตัวเลข เช่น 4500)\nแล้วแชร์โลเคชั่นหลังคา ผมจะคำนวณให้ทันที\n📞 095-774-4978"}])

def handle_location(reply_token,user_id,address):
    result=user_data.get(user_id)
    if result:
        flex=build_flex_json(result, location_text=f"📍 {address}")
        reply_message(reply_token,[
            {"type":"text","text":f"ได้รับพิกัด {address} แล้วครับ"},
            {"type":"flex","altText":f"ระบบ {result['system_kw']}kW ที่ {address}","contents":flex}
        ])
    else:
        reply_message(reply_token,[{"type":"text","text":f"ได้รับพิกัด {address} แล้วครับ ส่งบิลค่าไฟมาด้วยนะครับ"}])

@app.route("/", methods=['GET'])
def home(): return "Sawasdee Solar Agent V3 Fixed is running - 095-774-4978"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)))
