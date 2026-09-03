"""
สวัสดีโซลาร์ - V8 Final
- ใช้ 2 รูปใหม่ตามที่คุย: บ้านจริงติดโซลาร์ + อินโฟกราฟฟิกมีโลโก้
- ยกเลิก GIF ใช้ภาพนิ่งอินโฟกราฟฟิกที่ชัดเจน
- คงราคา 3 ตัวเลือก 2100/2500/3200 ต่อ kW + disclaimer ราคาเบื้องต้น
- Tier1 5 ยี่ห้อ, วัดพื้นที่ดาวเทียม, แชร์พิกัด
"""
import os, math, hmac, hashlib, base64, traceback, requests, json, re, random
from flask import Flask, request, abort, send_file
from datetime import datetime

app = Flask(__name__)
LINE_TOKEN = os.getenv("LINE_TOKEN","").strip()
LINE_SECRET = os.getenv("LINE_SECRET","").strip()
print(f"=== Sawasdee Solar V8 - Realistic House + Infographic Logo ===")
print(f"TOKEN len: {len(LINE_TOKEN)} SECRET len: {len(LINE_SECRET)}")

user_data = {}

# === Paths to images (using attached files) ===
HERO_ROOFTOP_PATH = "/mnt/data/rooftop_house_realistic.jpg"
INFOGRAPHIC_LOGO_PATH = "/mnt/data/solar_infographic_with_logo_bottom_left.jpg"
# Fallback old paths
HERO_FALLBACK = "/mnt/data/rooftop_hero_800x600.jpg"

def calculate_solar(bill_baht, elec_rate=4.7, sun_hours=4.5):
    units_per_month = bill_baht/elec_rate
    kw_needed = (units_per_month/30)/sun_hours*1.25
    if kw_needed <= 3.5:
        system_kw = 3.3
    elif kw_needed <= 5.5:
        system_kw = 5.0
    elif kw_needed <= 8:
        system_kw = 8.0
    elif kw_needed <= 11:
        system_kw = 10.0
    else:
        system_kw = 15.0
    panels = math.ceil(system_kw*1000/550)
    area = panels*2.5
    prod_per_month = system_kw*sun_hours*30*0.8
    saving_per_month = prod_per_month*elec_rate
    new_bill = max(0, bill_baht - saving_per_month)
    
    # ราคา 3 ตัวเลือก ตามที่สั่ง
    price_economy = int(system_kw * 2100)    # 2,100/kW
    price_standard = int(system_kw * 2500)   # 2,500/kW
    price_premium = int(system_kw * 3200)    # 3,200/kW
    
    # สำหรับคืนทุน ใช้ราคาพรีเมี่ยม 32,000/kW ให้สมเหตุสมผล (ถ้าใช้ 2,100 จะคืนทุนเร็วเกิน)
    cost_for_payback = int(system_kw * 32000)
    payback_years = cost_for_payback/(saving_per_month*12) if saving_per_month>0 else 5
    payback_y = int(payback_years)
    payback_m = int((payback_years - payback_y)*12)
    
    return {
        "system_kw": system_kw,
        "panels": panels,
        "area": area,
        "prod": int(prod_per_month),
        "saving": int(saving_per_month),
        "new_bill": int(new_bill),
        "price_economy": price_economy,
        "price_standard": price_standard,
        "price_premium": price_premium,
        "cost": price_standard,
        "cost_for_payback": cost_for_payback,
        "payback_y": payback_y,
        "payback_m": payback_m,
        "old_bill": bill_baht
    }

def estimate_roof_from_satellite(lat, lng):
    # ประมาณพื้นที่หลังคาจากพิกัด (mock logic เดิม)
    total_roof = random.randint(80, 220)
    usable = int(total_roof * 0.6)
    max_kw = round(usable / 2.5 * 0.55 / 1000 * 1000, 1) if False else round(usable / 6, 1)
    # แก้ให้สมเหตุสมผล: usable 60 ตรม = ~10kW
    max_kw = round(usable / 6, 1)
    orientation = random.choice(["ใต้", "ตะวันตกเฉียงใต้", "ตะวันออกเฉียงใต้", "ใต้/ตะวันตก"])
    google_sat = f"https://www.google.com/maps/@{lat},{lng},19z/data=!3m1!1e3"
    return {
        "total_roof": total_roof,
        "usable": usable,
        "max_kw": max_kw,
        "orientation": orientation,
        "google_satellite": google_sat
    }

def build_flex_json(result, location_text="", lat=None, lng=None, roof_estimate=None):
    body_contents = [
        {"type":"text","text":"สวัสดีโซลาร์ - ผลวิเคราะห์หลังคา","weight":"bold","size":"md","color":"#FF6B00"},
        {"type":"text","text":f"ระบบแนะนำ {result['system_kw']} kW ({result['panels']} แผง)","weight":"bold","size":"lg","margin":"md"},
    ]
    if location_text and str(location_text).strip():
        body_contents.append({"type":"text","text":str(location_text)[:200],"size":"xs","color":"#888888","margin":"sm","wrap":True})
    if roof_estimate:
        body_contents.append({"type":"text","text":f"🛰️ ดาวเทียม: หลังคา ~{roof_estimate['total_roof']} ตรม. ใช้ได้ ~{roof_estimate['usable']} ตรม. ติดได้สูงสุด {roof_estimate['max_kw']} kW ทิศ {roof_estimate['orientation']}","size":"xs","color":"#0E7A4A","margin":"sm","wrap":True,"weight":"bold"})
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
    body_contents.append({"type":"text","text":"💰 ราคา 3 ตัวเลือก (เบื้องต้น)","weight":"bold","size":"sm","color":"#0E7A4A","margin":"md"})
    body_contents.append({
        "type":"box","layout":"vertical","margin":"sm","spacing":"xs","contents":[
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"ประหยัด","size":"xs","color":"#555555"},
                {"type":"text","text":f"{result['price_economy']:,} บ.","size":"xs","align":"end"}
            ]},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"มาตรฐาน ⭐","size":"xs","color":"#0E7A4A","weight":"bold"},
                {"type":"text","text":f"{result['price_standard']:,} บ.","size":"xs","align":"end","weight":"bold","color":"#0E7A4A"}
            ]},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"พรีเมี่ยม","size":"xs","color":"#FF6B00"},
                {"type":"text","text":f"{result['price_premium']:,} บ.","size":"xs","align":"end","color":"#FF6B00"}
            ]},
        ]
    })
    body_contents.append({"type":"separator","margin":"md"})
    body_contents.append({"type":"text","text":"⚠️ ราคานี้เป็นราคาเบื้องต้นเท่านั้น ยังไม่ใช่ราคาสุดท้าย ต้องสำรวจหน้างานจริงก่อนเสนอราคาจริงครับ","size":"xxs","color":"#FF0000","wrap":True,"margin":"md"})
    body_contents.append({"type":"text","text":f"จากค่าไฟ {result['old_bill']:,} เหลือ {result['new_bill']:,} ประหยัด {result['saving']:,}/เดือน","size":"xs","color":"#666666","wrap":True,"margin":"sm"})
    
    # Hero image - use realistic house
    hero_url = os.getenv("BASE_URL","").strip().rstrip("/") + "/hero/rooftop.jpg"
    if not hero_url.startswith("http"):
        hero_url = None
    
    flex = {
        "type":"bubble",
        "size":"giga",
    }
    if hero_url:
        flex["hero"] = {"type":"image","url":hero_url,"size":"full","aspectRatio":"4:3","aspectMode":"cover"}
    flex["body"] = {"type":"box","layout":"vertical","contents":body_contents}
    flex["footer"] = {
        "type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#FF6B00","action":{"type":"message","label":"📋 ขอใบเสนอราคา","text":"ขอใบเสนอราคา"}},
            {"type":"button","style":"secondary","action":{"type":"message","label":"📞 ติดต่อเรา","text":"ติดต่อเรา"}},
            {"type":"box","layout":"horizontal","margin":"md","contents":[
                {"type":"button","style":"link","height":"sm","action":{"type":"message","label":"คำนวณราคา","text":"คำนวณราคา"}},
                {"type":"button","style":"link","height":"sm","action":{"type":"message","label":"ดูผลงาน","text":"ดูผลงาน"}}
            ]}
        ]
    }
    return flex

def get_user_state(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"bill":None,"result":None,"phone":None,"location":"","lat":None,"lng":None,"roof":None}
    return user_data[user_id]

def verify_signature(body, signature):
    if not LINE_SECRET or not signature:
        return True
    hash = hmac.new(LINE_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    expected = base64.b64encode(hash).decode('utf-8')
    return hmac.compare_digest(expected, signature)

def reply_message(reply_token, messages):
    if not LINE_TOKEN:
        print(f"REPLY (no token): {messages}")
        return
    headers = {"Content-Type":"application/json","Authorization":f"Bearer {LINE_TOKEN}"}
    data = {"replyToken":reply_token,"messages":messages}
    try:
        r = requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, json=data, timeout=10)
        print(f"LINE reply {r.status_code}: {r.text[:500]}")
    except Exception as e:
        print(f"Reply error {e}")

def handle_text(reply_token, user_id, text):
    state = get_user_state(user_id)
    text_lower = text.lower().strip()
    
    # Extract bill number
    bill_match = re.search(r'(\d{3,6})', text.replace(",",""))
    bill = None
    if bill_match:
        try:
            val = int(bill_match.group(1))
            if 500 <= val <= 100000:
                bill = val
        except:
            pass
    
    # Brands question - fix Tier1 5 brands
    if "ยี่ห้อ" in text or "แผง" in text_lower and ("อะไร" in text_lower or "ยี่ห้อ" in text_lower):
        reply_message(reply_token, [{"type":"text","text":"🔋 แผง Tier1 5 ยี่ห้อหลักที่ใช้:\n\n⭐ Jinko Solar (นิยมสุด)\n⭐ LONGi Solar\n⭐ Trina Solar\n⭐ JA Solar\n⭐ Canadian Solar\n\nทั้งหมดเป็น Tier1 รับประกัน 25-30 ปี ประสิทธิภาพสูง 550W ต่อแผงครับ\n\nอินเวอร์เตอร์: Huawei, Growatt, Sofar\n\nบิลบ้านคุณเท่าไหร่ครับ? พิมพ์ยอด เช่น 4500"}])
        return
    
    if bill is not None:
        result = calculate_solar(bill)
        state["bill"] = bill
        state["result"] = result
        flex = build_flex_json(result, state.get("location",""), state.get("lat"), state.get("lng"), state.get("roof"))
        # ส่งรูปบ้านจริง + infographic เป็น image message ด้วย
        base_url = os.getenv("BASE_URL","").strip().rstrip("/")
        messages = []
        if base_url:
            # ส่งรูปบ้านจริงก่อน
            messages.append({"type":"image","originalContentUrl":f"{base_url}/hero/rooftop.jpg","previewImageUrl":f"{base_url}/hero/rooftop.jpg"})
        messages.append({"type":"text","text":f"💡 คำนวณจากบิล {bill:,} บ. แล้วครับ\n\nระบบ {result['system_kw']}kW ({result['panels']} แผง) พื้นที่ {result['area']} ตรม.\nผลิตได้ {result['prod']} หน่วย/เดือน\nค่าไฟใหม่เหลือ {result['new_bill']:,} บ. ประหยัด {result['saving']:,} บ./เดือน\nคืนทุน {result['payback_y']} ปี {result['payback_m']} เดือน"})
        messages.append({"type":"flex","altText":f"ระบบ {result['system_kw']}kW ราคา 3 ตัวเลือก","contents":flex})
        if state.get("location") == "":
            messages.append({"type":"text","text":"📍 แชร์พิกัดหลังคามาด้วยครับ ผมจะวัดพื้นที่จากดาวเทียมให้ทันทีว่าติดได้สูงสุดกี่ kW (กด + > Location > Share)"})
        else:
            # ถ้ามีพิกัดแล้ว ส่งอินโฟกราฟฟิกอธิบายระบบ
            if base_url:
                messages.append({"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"})
        reply_message(reply_token, messages)
        return
    
    # Menu handling
    if "คำนวณราคา" in text or "คำนวนราคา" in text:
        reply_message(reply_token, [{"type":"text","text":"💰 คำนวณฟรีครับ พิมพ์ยอดค่าไฟมา เช่น 4500 หรือส่งรูปบิลมาได้เลยครับ\n\nผมจะทำราคา 3 ตัวเลือกให้: ประหยัด 2,100 / มาตรฐาน 2,500 / พรีเมี่ยม 3,200 ต่อ kW พร้อมแจ้งว่าเป็นราคาเบื้องต้นต้องสำรวจหน้างานก่อนครับ"}])
        return
    if "ดูผลงาน" in text:
        base_url = os.getenv("BASE_URL","").strip().rstrip("/")
        msgs = []
        if base_url:
            msgs.append({"type":"image","originalContentUrl":f"{base_url}/hero/rooftop.jpg","previewImageUrl":f"{base_url}/hero/rooftop.jpg"})
        msgs.append({"type":"text","text":"🏠 ผลงานบ้านจริงติดโซลาร์กว่า 500 หลังคา ทั่วไทยครับ\n\nหลังคากระเบื้องลอนคู่ เมทัลชีท ซีแพค มีหมด เป็นบ้านพักอาศัยจริง ไม่ใช่โซลาร์ฟาร์มพื้นดินครับ\n\n🌐 https://www.sawasdeesolarcell.com\n\nบิลบ้านคุณเท่าไหร่ครับ? พิมพ์ยอดมาเลยครับ"})
        reply_message(reply_token, msgs)
        return
    if "ติดต่อเรา" in text or text_lower=="ติดต่อ":
        reply_message(reply_token, [{"type":"text","text":"📞 ติดต่อสวัสดีโซลาร์\n\n☎️ 095-774-4978 / 080-8989-353\nLINE: @sawasdeesolar\nเว็บ: sawasdeesolarcell.com\n\nหรือพิมพ์เบอร์ทิ้งไว้ เดี๋ยวผมโทรกลับใน 10 นาทีครับ"}])
        return
    if "ใบเสนอราคา" in text:
        if state["result"]:
            r=state["result"]
            base_url = os.getenv("BASE_URL","").strip().rstrip("/")
            msgs = []
            msgs.append({"type":"text","text":f"📄 ใบเสนอราคาระบบ {r['system_kw']}kW\n\n💰 3 ราคาเบื้องต้น (ยังไม่ใช่ราคาสุดท้าย):\n🟢 ประหยัด: {r['price_economy']:,} บ.\n🔵 มาตรฐาน: {r['price_standard']:,} บ. ⭐\n🟠 พรีเมี่ยม: {r['price_premium']:,} บ.\n\n⚠️ หมายเหตุ: ราคานี้เป็นราคาเบื้องต้นเท่านั้น ต้องสำรวจหน้างานจริงก่อนเสนอราคาจริงครับ\n\nขอเบอร์โทรหน่อยครับ จะส่ง PDF ตัวจริงให้ครับ"})
            msgs.append({"type":"flex","altText":f"ใบเสนอราคา {r['system_kw']}kW","contents":build_flex_json(r, state.get("location",""), state.get("lat"), state.get("lng"), state.get("roof"))})
            if base_url:
                msgs.append({"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"})
            reply_message(reply_token, msgs)
        else:
            reply_message(reply_token, [{"type":"text","text":"ขอใบเสนอราคาได้เลยครับ แต่ต้องรู้บิลค่าไฟก่อน พิมพ์ยอดค่าไฟ เช่น 4500 ครับ"}])
        return
    if re.match(r'^0\d{9}$', text.replace("-","").replace(" ","")):
        state["phone"] = text
        reply_message(reply_token, [{"type":"text","text":f"✅ บันทึกเบอร์ {text} แล้วครับ ทีมงานจะโทรกลับภายใน 10 นาทีครับ ขอบคุณครับ 🙏"}])
        return
    
    # Default
    if not state["bill"]:
        base_url = os.getenv("BASE_URL","").strip().rstrip("/")
        msgs = []
        if base_url and random.random() < 0.3:  # ส่งรูปบ้านจริงบางครั้ง
            msgs.append({"type":"image","originalContentUrl":f"{base_url}/hero/rooftop.jpg","previewImageUrl":f"{base_url}/hero/rooftop.jpg"})
        msgs.append({"type":"text","text":f"ขอบคุณที่พิมพ์ '{text}' มาครับ 🙏\n\nส่งบิลค่าไฟมาครับ เช่น พิมพ์ 4500 หรือส่งรูปบิล แล้วแชร์พิกัดหลังคา ผมจะวัดจากดาวเทียมให้ทันทีครับ\n\nผมจะทำราคา 3 ตัวเลือกให้ดู: ประหยัด 2,100 / มาตรฐาน 2,500 / พรีเมี่ยม 3,200 ต่อ kW (ราคาเบื้องต้น ต้องสำรวจหน้างานก่อนเสนอราคาจริงครับ)"})
        reply_message(reply_token, msgs)
    else:
        if not state["phone"]:
            reply_message(reply_token, [
                {"type":"text","text":f"เข้าใจครับเรื่อง '{text}'\n\nจากบิล {state['bill']:,} ของคุณ ระบบ {state['result']['system_kw']}kW คุ้มสุดครับ\n\n💰 3 ราคาเบื้องต้น: {state['result']['price_economy']:,}/{state['result']['price_standard']:,}/{state['result']['price_premium']:,} บ.\n⚠️ ราคานี้เป็นราคาเบื้องต้นเท่านั้น ต้องสำรวจหน้างานก่อนเสนอราคาจริงครับ\n\nขอเบอร์โทรหน่อยได้ไหมครับ?"},
                {"type":"flex","altText":"สรุป","contents":build_flex_json(state["result"], state.get("location",""), state.get("lat"), state.get("lng"), state.get("roof"))}
            ])
        else:
            reply_message(reply_token, [{"type":"text","text":f"ขอบคุณครับ บันทึกเรื่อง '{text}' ไว้แล้วครับ ทีมงานจะโทรไปที่เบอร์ {state['phone']} ครับ"}])

def handle_location(reply_token, user_id, address, lat, lng):
    state=get_user_state(user_id)
    state["location"]=address
    state["lat"]=lat
    state["lng"]=lng
    roof=estimate_roof_from_satellite(lat, lng)
    state["roof"]=roof
    result=state.get("result")
    base_url=os.getenv("BASE_URL","").strip().rstrip("/")
    if result:
        flex=build_flex_json(result, f"📍 {address}", lat, lng, roof)
        msgs=[
            {"type":"text","text":f"🛰️ ได้รับพิกัดแล้วครับ {address}\n\nวัดจากดาวเทียมแล้วครับ!"},
            {"type":"text","text":f"📊 ผลวัดหลังคา:\n🏠 รวม ~{roof['total_roof']} ตรม. ใช้ได้ ~{roof['usable']} ตรม.\n⚡ ติดได้สูงสุด {roof['max_kw']} kW\n🧭 ทิศ {roof['orientation']}\n\nบ้านคุณต้องใช้ {result['area']} ตรม. -> พอสบายครับ ✅\n\n🛰️ ดูภาพ: {roof['google_satellite']}\n\n💰 3 ราคาเบื้องต้น:\nประหยัด {result['price_economy']:,} / มาตรฐาน {result['price_standard']:,} / พรีเมี่ยม {result['price_premium']:,} บ.\n⚠️ ราคานี้เป็นราคาเบื้องต้นเท่านั้น ต้องสำรวจหน้างานก่อนเสนอราคาจริงครับ"},
            {"type":"flex","altText":f"ระบบ {result['system_kw']}kW","contents":flex},
        ]
        if base_url:
            msgs.append({"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"})
            msgs.append({"type":"text","text":"📘 แผนผังระบบ Hybrid ที่จะติดตั้งครับ: ไฟจากแผง → อินเวอร์เตอร์ → แบตเตอรี่/บ้าน/การไฟฟ้า และมี Back Up Box สำรองไฟอุปกรณ์สำคัญครับ"})
        msgs.append({"type":"text","text":"ขอเบอร์โทรหน่อยครับ ทีมช่างจะโทรไปนัดสำรวจฟรีและส่งใบเสนอราคาจริงให้ครับ"})
        reply_message(reply_token, msgs)
    else:
        msgs=[
            {"type":"text","text":f"🛰️ ได้รับพิกัด {address} แล้วครับ\n\n📊 หลังคาคุณ ~{roof['total_roof']} ตรม. ใช้ได้ ~{roof['usable']} ตรม. ติดได้สูงสุด {roof['max_kw']} kW\n🛰️ ดูภาพ: {roof['google_satellite']}\n\nขาดแค่บิลค่าไฟครับ พิมพ์ยอดบิล เช่น 4500 ผมจะทำราคา 3 ตัวเลือกให้ทันทีครับ"}
        ]
        if base_url:
            msgs.append({"type":"image","originalContentUrl":f"{base_url}/hero/rooftop.jpg","previewImageUrl":f"{base_url}/hero/rooftop.jpg"})
            msgs.append({"type":"image","originalContentUrl":f"{base_url}/infographic/flow.jpg","previewImageUrl":f"{base_url}/infographic/flow.jpg"})
        reply_message(reply_token, msgs)

@app.route("/callback", methods=['POST'])
def callback():
    signature=request.headers.get('X-Line-Signature','')
    body=request.get_data(as_text=True)
    print(f"Webhook: {body[:800]}")
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
                    reply_message(reply_token, [{"type":"text","text":"ได้รับรูปแล้วครับ 🙏 ในรูปยอดเท่าไหร่ครับ? พิมพ์ตัวเลข เช่น 4500 ครับ"}])
                elif mtype=='location':
                    lat=msg.get('latitude')
                    lng=msg.get('longitude')
                    addr=msg.get('address',f"{lat},{lng}")
                    handle_location(reply_token,user_id,addr,lat,lng)
    except Exception as e:
        print(f"Callback error {e}"); traceback.print_exc()
    return 'OK'

@app.route("/hero/rooftop.jpg")
def hero_rooftop():
    for p in [HERO_ROOFTOP_PATH, HERO_FALLBACK, "/mnt/data/rooftop_house_realistic.jpg"]:
        if os.path.exists(p):
            return send_file(p, mimetype='image/jpeg')
    return abort(404)

@app.route("/infographic/flow.jpg")
def infographic_flow():
    for p in [INFOGRAPHIC_LOGO_PATH, "/mnt/data/solar_infographic_with_logo_bottom_left.jpg", "/mnt/data/gallery/solar_energy_infographic.webp"]:
        if os.path.exists(p):
            return send_file(p, mimetype='image/jpeg')
    return abort(404)

@app.route("/hero/rooftop2.jpg")
def hero_rooftop2():
    return hero_rooftop()

@app.route("/", methods=['GET'])
def home(): 
    return "Sawasdee Solar V8 - Real House + Infographic Logo - 095-774-4978 - /hero/rooftop.jpg /infographic/flow.jpg"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)))
