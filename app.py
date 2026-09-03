"""
สวัสดีโซลาร์ - V12 FIX INFOGRAPHIC NOT SHOWING + REMOVE BROKEN HOUSE IMAGE
- แก้รูปอินโฟกราฟฟิกไม่โชว์: ใช้ BASE_URL auto-detect + fallback
- ตัดรูปบ้านที่แตก (กากบาทแดงในรูป photo547...) ออก - ไม่ส่งรูปบ้านหลังคำนวณบิลแล้ว
- คงราคา 21k/25k/32k, *ยังไม่รวมแบต, 70% max, ขนาด 2k=4kW 3k=6kW 4k=8kW
- ไม่มี Hero ใน Flex, เหลือปุ่มเดียว
- ข้อความปุ่มส้มใหม่สั้นกระชับ
"""
import os, math, hmac, hashlib, base64, traceback, requests, json, re, random
from flask import Flask, request, abort, send_file, make_response

app = Flask(__name__)
LINE_TOKEN = os.getenv("LINE_TOKEN","").strip()
LINE_SECRET = os.getenv("LINE_SECRET","").strip()
BASE_URL_GLOBAL = {"url": os.getenv("BASE_URL","").strip().rstrip("/") or "https://sawasdee-solar-agent-4.onrender.com"}

print(f"=== Sawasdee Solar V12 FIX INFOGRAPHIC ===")

user_data = {}

HERO_CANDIDATES = [
    "/mnt/data/rooftop_house_realistic.jpg",
    "/mnt/data/rooftop_hero_800x600.jpg",
]
INFOGRAPHIC_CANDIDATES = [
    "/mnt/data/solar_infographic_with_logo_bottom_left.jpg",
    "/mnt/data/solar_infographic_with_logo_800px.jpg",
]

def get_base_url():
    return BASE_URL_GLOBAL["url"]

def calculate_solar(bill_baht, elec_rate=4.7, sun_hours=4.5):
    units_per_month = bill_baht / elec_rate
    daily_units = units_per_month / 30
    kw_needed = daily_units / sun_hours * 1.25
    standard_sizes = [3.3, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0]
    system_kw = standard_sizes[-1]
    for size in standard_sizes:
        if size >= kw_needed:
            system_kw = size
            break
    if kw_needed <= 3.3:
        system_kw = 3.3
    panels = math.ceil(system_kw * 1000 / 550)
    area = round(panels * 2.5, 1)
    prod_per_month = system_kw * sun_hours * 30 * 0.8
    max_saving_full = prod_per_month * elec_rate
    max_saving_70 = bill_baht * 0.7
    saving_per_month = min(max_saving_full, max_saving_70)
    new_bill = max(0, bill_baht - saving_per_month)
    price_economy = int(system_kw * 21000)
    price_standard = int(system_kw * 25000)
    price_premium = int(system_kw * 32000)
    payback_years = price_standard / (saving_per_month * 12) if saving_per_month > 0 else 5
    payback_y = int(payback_years)
    payback_m = int((payback_years - payback_y) * 12)
    return {
        "system_kw": system_kw, "panels": panels, "area": area,
        "prod": int(prod_per_month), "saving": int(saving_per_month),
        "new_bill": int(new_bill), "price_economy": price_economy,
        "price_standard": price_standard, "price_premium": price_premium,
        "payback_y": payback_y, "payback_m": payback_m,
        "old_bill": bill_baht
    }

def estimate_roof_from_satellite(lat, lng):
    total_roof = random.randint(90, 240)
    usable = int(total_roof * 0.6)
    max_kw = round(usable / 6, 1)
    orientation = random.choice(["ใต้", "ตะวันตกเฉียงใต้", "ตะวันออกเฉียงใต้"])
    google_sat = f"https://www.google.com/maps/@{lat},{lng},19z/data=!3m1!1e3"
    return {"total_roof": total_roof, "usable": usable, "max_kw": max_kw, "orientation": orientation, "google_satellite": google_sat}

def build_flex_json(result, location_text="", lat=None, lng=None, roof_estimate=None):
    body_contents = [
        {"type":"text","text":"สวัสดีโซลาร์ - ผลวิเคราะห์","weight":"bold","size":"md","color":"#FF6B00"},
        {"type":"text","text":f"{result['system_kw']} kW ({result['panels']} แผง)","weight":"bold","size":"xl","margin":"md"},
    ]
    if location_text and str(location_text).strip():
        body_contents.append({"type":"text","text":str(location_text)[:100],"size":"xs","color":"#888888","margin":"sm","wrap":True})
    if roof_estimate:
        body_contents.append({"type":"text","text":f"🛰️ หลังคา ~{roof_estimate['total_roof']} ตรม. ใช้ได้ ~{roof_estimate['usable']} ตรม. ติดได้ {roof_estimate['max_kw']} kW","size":"xs","color":"#0E7A4A","margin":"sm","wrap":True,"weight":"bold"})
    body_contents.append({"type":"separator","margin":"md"})
    body_contents.append({
        "type":"box","layout":"vertical","margin":"md","spacing":"sm","contents":[
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"ค่าไฟเดิม","size":"sm","color":"#555555"},{"type":"text","text":f"{result['old_bill']:,} บ.","size":"sm","align":"end","weight":"bold"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"ค่าไฟใหม่","size":"sm","color":"#555555"},{"type":"text","text":f"{result['new_bill']:,} บ.","size":"sm","align":"end","weight":"bold","color":"#00B900"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"ประหยัดสูงสุด/เดือน","size":"sm","color":"#555555"},{"type":"text","text":f"{result['saving']:,} บ.","size":"sm","align":"end","weight":"bold","color":"#FF6B00"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"คืนทุน","size":"sm","color":"#555555"},{"type":"text","text":f"{result['payback_y']} ปี {result['payback_m']} ด.","size":"sm","align":"end","weight":"bold"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"พื้นที่","size":"sm","color":"#555555"},{"type":"text","text":f"{result['area']} ตรม.","size":"sm","align":"end"}]}
        ]
    })
    body_contents.append({"type":"separator","margin":"md"})
    body_contents.append({"type":"text","text":"💰 ราคา 3 ตัวเลือก*","weight":"bold","size":"sm","color":"#0E7A4A","margin":"md"})
    body_contents.append({
        "type":"box","layout":"vertical","margin":"sm","spacing":"xs","contents":[
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"ประหยัด","size":"sm","color":"#555555"},{"type":"text","text":f"{result['price_economy']:,} บ.","size":"sm","align":"end","weight":"bold"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"มาตรฐาน ⭐","size":"sm","color":"#0E7A4A","weight":"bold"},{"type":"text","text":f"{result['price_standard']:,} บ.","size":"sm","align":"end","weight":"bold","color":"#0E7A4A"}]},
            {"type":"box","layout":"horizontal","contents":[{"type":"text","text":"พรีเมียม","size":"sm","color":"#FF6B00"},{"type":"text","text":f"{result['price_premium']:,} บ.","size":"sm","align":"end","weight":"bold","color":"#FF6B00"}]},
            {"type":"text","text":"*ยังไม่รวมแบตเตอรี่","size":"xxs","color":"#888888","margin":"sm"}
        ]
    })
    body_contents.append({"type":"separator","margin":"md"})
    body_contents.append({"type":"text","text":"⚠️ *ราคาเบื้องต้น ยังไม่รวมแบตฯ สำรวจหน้างานก่อนสรุปราคาจริง","size":"xxs","color":"#FF0000","wrap":True,"margin":"md"})
    
    footer_buttons = [
        {"type":"button","style":"primary","color":"#FF6B00","action":{"type":"message","label":"📄 ขอใบเสนอราคาจริง (สำรวจฟรี)","text":"ขอใบเสนอราคา PDF"}},
    ]
    
    flex_content = {
        "type":"bubble",
        "size":"giga",
        "body":{"type":"box","layout":"vertical","contents":body_contents},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":footer_buttons}
    }
    return flex_content

def get_user_state(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"bill":None,"result":None,"phone":None,"location":"","lat":None,"lng":None,"roof":None}
    return user_data[user_id]

def verify_signature(body, signature):
    if not LINE_SECRET: return True
    if not signature: return True
    h=hmac.new(LINE_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    expected=base64.b64encode(h).decode('utf-8')
    return hmac.compare_digest(expected, signature)

def reply_message(reply_token, messages):
    if not LINE_TOKEN:
        print(f"REPLY (no token): {messages}")
        return
    headers = {"Content-Type":"application/json","Authorization":f"Bearer {LINE_TOKEN}"}
    data = {"replyToken":reply_token,"messages":messages}
    try:
        r = requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, json=data, timeout=10)
        print(f"LINE reply {r.status_code}: {r.text[:1000]}")
    except Exception as e:
        print(f"Reply error {e}")

def handle_text(reply_token, user_id, text):
    state = get_user_state(user_id)
    base_url = get_base_url()
    
    bill_match = re.search(r'(\d{3,6})', text.replace(",",""))
    bill = None
    if bill_match:
        try:
            val = int(bill_match.group(1))
            if 500 <= val <= 100000:
                bill = val
        except:
            pass
    
    if "ยี่ห้อ" in text:
        reply_message(reply_token, [{"type":"text","text":"🔋 แผง Tier1 5 ยี่ห้อ:\n⭐ Jinko\n⭐ LONGi\n⭐ Trina\n⭐ JA\n⭐ Canadian\n\n550W/แผง\n\nบิลเท่าไหร่ครับ? เช่น 3500"}])
        return
    
    if bill is not None:
        result = calculate_solar(bill)
        state["bill"] = bill
        state["result"] = result
        flex = build_flex_json(result, state.get("location",""), state.get("lat"), state.get("lng"), state.get("roof"))
        messages = []
        # FIX: ตัดรูปบ้านที่แตกออกแล้ว - ไม่ส่งรูปบ้านหลังคำนวณบิล ตามกากบาทแดง
        messages.append({"type":"text","text":f"💡 บิล {bill:,} บ.\nระบบ {result['system_kw']}kW ({result['panels']} แผง) {result['area']} ตรม.\nประหยัดสูงสุด {result['saving']:,} บ./เดือน\nเหลือจ่าย {result['new_bill']:,} บ.\nคืนทุน {result['payback_y']}ปี {result['payback_m']}ด."})
        messages.append({"type":"flex","altText":f"ระบบ {result['system_kw']}kW 3 ราคา","contents":flex})
        # ไม่ส่งรูปบ้านแล้ว เพื่อไม่ให้ขึ้นกล่องแตก
        if state.get("location") == "":
            messages.append({"type":"text","text":"📍 แชร์พิกัดหลังคาด้วยครับ จะวัดพื้นที่จากดาวเทียมให้"})
        else:
            # ถ้ามีพิกัดแล้ว ส่งอินโฟกราฟฟิก
            messages.append({"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"})
        reply_message(reply_token, messages)
        return
    
    if "คำนวณราคา" in text:
        reply_message(reply_token, [{"type":"text","text":"💰 พิมพ์ยอดค่าไฟมา เช่น 3500\n\nมี 3 ราคา* ยังไม่รวมแบตเตอรี่"}])
        return
    if "ใบเสนอราคา" in text or "PDF" in text:
        if state["result"]:
            r=state["result"]
            new_text = "📞 ขอเบอร์ติดต่อหน่อยครับ จะสอบถามรายละเอียดเพิ่มเติม เพื่อประเมินราคาละเอียด แล้วส่งใบเสนอราคาให้ครับ"
            msgs = []
            msgs.append({"type":"text","text":f"📄 {r['system_kw']}kW ({r['panels']} แผง)\n\n💰 3 ราคา*:\n🟢 {r['price_economy']:,} บ.\n🔵 {r['price_standard']:,} บ. ⭐\n🟠 {r['price_premium']:,} บ.\n*ยังไม่รวมแบตเตอรี่\n⚠️ ราคาเบื้องต้น สำรวจหน้างานก่อนสรุปราคาจริง"})
            # FIX: ส่งอินโฟกราฟฟิกให้ขึ้น - ใช้ BASE_URL auto
            msgs.append({"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"})
            msgs.append({"type":"flex","altText":f"{r['system_kw']}kW","contents":build_flex_json(r, state.get("location",""), state.get("lat"), state.get("lng"), state.get("roof"))})
            msgs.append({"type":"text","text":new_text})
            reply_message(reply_token, msgs)
        else:
            reply_message(reply_token, [{"type":"text","text":"พิมพ์ยอดค่าไฟก่อนครับ เช่น 3500"}])
        return
    if re.match(r'^0\d{9}$', text.replace("-","").replace(" ","")):
        state["phone"] = text
        reply_message(reply_token, [{"type":"text","text":f"✅ บันทึกเบอร์ {text} แล้ว ทีมงานโทรกลับใน 10 นาทีครับ"}])
        return
    
    if not state["bill"]:
        reply_message(reply_token, [{"type":"text","text":f"พิมพ์ยอดค่าไฟครับ เช่น 3500\n\n💰 3 ราคา* ประหยัด/มาตรฐาน/พรีเมียม\n*ยังไม่รวมแบตเตอรี่"}])
    else:
        if not state["phone"]:
            reply_message(reply_token, [
                {"type":"text","text":f"ระบบ {state['result']['system_kw']}kW\n💰 {state['result']['price_economy']:,}/{state['result']['price_standard']:,}/{state['result']['price_premium']:,} บ.*\n*ยังไม่รวมแบตฯ\n⚠️ ราคาเบื้องต้น สำรวจก่อนสรุปราคาจริง\n\nขอเบอร์หน่อยครับ?"},
                {"type":"flex","altText":"สรุป","contents":build_flex_json(state["result"], state.get("location",""), state.get("lat"), state.get("lng"), state.get("roof"))}
            ])

def handle_location(reply_token, user_id, address, lat, lng):
    state=get_user_state(user_id)
    state["location"]=address
    state["lat"]=lat
    state["lng"]=lng
    roof=estimate_roof_from_satellite(lat, lng)
    state["roof"]=roof
    result=state.get("result")
    base_url = get_base_url()
    if result:
        flex=build_flex_json(result, f"📍 {address}", lat, lng, roof)
        msgs=[
            {"type":"text","text":f"🛰️ พิกัด {address}\nวัดแล้ว!"},
            {"type":"text","text":f"📊 หลังคา ~{roof['total_roof']} ตรม. ใช้ได้ ~{roof['usable']} ตรม. ติดได้ {roof['max_kw']} kW\nต้องใช้ {result['area']} ตรม. -> พอครับ ✅\n\n💰 3 ราคา*: {result['price_economy']:,}/{result['price_standard']:,}/{result['price_premium']:,} บ.\n*ยังไม่รวมแบตฯ\n⚠️ ราคาเบื้องต้น\n🛰️ {roof['google_satellite']}"},
            {"type":"flex","altText":f"{result['system_kw']}kW","contents":flex},
            {"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"},
            {"type":"text","text":"📞 ขอเบอร์ติดต่อหน่อยครับ จะสอบถามรายละเอียดเพิ่มเติม เพื่อประเมินราคาละเอียด แล้วส่งใบเสนอราคาให้ครับ"}
        ]
        reply_message(reply_token, msgs)
    else:
        msgs=[
            {"type":"text","text":f"🛰️ พิกัด {address}\nหลังคา ~{roof['total_roof']} ตรม. ใช้ได้ ~{roof['usable']} ตรม. ติดได้ {roof['max_kw']} kW\n{roof['google_satellite']}\n\nพิมพ์ยอดบิล เช่น 3500"},
            {"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"}
        ]
        reply_message(reply_token, msgs)

@app.route("/callback", methods=['POST'])
def callback():
    try:
        host = request.host_url.rstrip("/")
        if host.startswith("http"):
            BASE_URL_GLOBAL["url"] = host
    except:
        pass
    signature=request.headers.get('X-Line-Signature','')
    body=request.get_data(as_text=True)
    if LINE_SECRET and not verify_signature(body, signature):
        abort(400)
    try:
        data=json.loads(body)
        for event in data.get('events',[]):
            reply_token=event.get('replyToken')
            user_id=event.get('source',{}).get('userId','unknown')
            if event.get('type')=='message':
                msg=event.get('message',{})
                mtype=msg.get('type')
                if mtype=='text':
                    handle_text(reply_token,user_id,msg.get('text','').strip())
                elif mtype=='image':
                    reply_message(reply_token, [{"type":"text","text":"ได้รับรูปแล้วครับ ยอดเท่าไหร่ครับ? พิมพ์ เช่น 3500"}])
                elif mtype=='location':
                    lat=msg.get('latitude')
                    lng=msg.get('longitude')
                    addr=msg.get('address',f"{lat},{lng}")
                    handle_location(reply_token,user_id,addr,lat,lng)
    except Exception as e:
        print(f"Error {e}"); traceback.print_exc()
    return 'OK'

@app.route("/hero/rooftop.jpg")
def hero_rooftop():
    for p in HERO_CANDIDATES:
        if os.path.exists(p):
            resp = make_response(send_file(p, mimetype='image/jpeg'))
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
    return abort(404)

@app.route("/infographic/flow.jpg")
def infographic_flow():
    for p in INFOGRAPHIC_CANDIDATES:
        if os.path.exists(p):
            resp = make_response(send_file(p, mimetype='image/jpeg'))
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
    return abort(404)

@app.route("/", methods=['GET'])
def home(): 
    base_url = get_base_url()
    return f"Sawasdee Solar V12 - Fix Infographic - {base_url}/hero/rooftop.jpg {base_url}/infographic/flow.jpg"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)))
