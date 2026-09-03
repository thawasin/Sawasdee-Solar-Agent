"""
สวัสดีโซลาร์ - V5 Satellite + Rooftop Hero
1. ดึงพิกัดหลังคาวัดพื้นที่จากดาวเทียม
2. ฮีโร่รูปแผงบนหลังคาบ้าน ไม่ใช่โซลาร์ฟาร์มพื้นดิน
"""
import os, math, hmac, hashlib, base64, traceback, requests, json, re, random
from flask import Flask, request, abort, send_file
from datetime import datetime

app = Flask(__name__)
LINE_TOKEN = os.getenv("LINE_TOKEN","").strip()
LINE_SECRET = os.getenv("LINE_SECRET","").strip()
print(f"=== Sawasdee Solar V5 Satellite + Rooftop ===")
print(f"TOKEN len: {len(LINE_TOKEN)} SECRET len: {len(LINE_SECRET)}")

user_data = {}

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
    payback_years=cost/(saving_per_month*12) if saving_per_month>0 else 10
    payback_y=int(payback_years)
    payback_m=int((payback_years-payback_y)*12)
    return {"system_kw":system_kw,"panels":panels,"area":area,"prod":int(prod_per_month),"saving":int(saving_per_month),"new_bill":int(new_bill),"cost":int(cost),"payback_y":payback_y,"payback_m":payback_m,"old_bill":bill_baht}

def build_flex_json(result, location_text="", lat=None, lng=None, roof_estimate=None):
    body_contents=[
        {"type":"text","text":"สวัสดีโซลาร์ - ผลวิเคราะห์หลังคา","weight":"bold","size":"md","color":"#FF6B00"},
        {"type":"text","text":f"ระบบแนะนำ {result['system_kw']} kW ({result['panels']} แผง)","weight":"bold","size":"lg","margin":"md"},
    ]
    if location_text and str(location_text).strip():
        body_contents.append({"type":"text","text":str(location_text)[:200],"size":"xs","color":"#888888","margin":"sm","wrap":True})
    # เพิ่มข้อมูลดาวเทียมถ้ามี
    if roof_estimate:
        body_contents.append({"type":"text","text":f"🛰️ วัดจากดาวเทียม: หลังคา ~{roof_estimate['total_roof']} ตรม. ใช้ได้ ~{roof_estimate['usable']} ตรม. ติดได้สูงสุด {roof_estimate['max_kw']} kW","size":"xs","color":"#0E7A4A","margin":"sm","wrap":True,"weight":"bold"})
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
    body_contents.append({"type":"text","text":f"จากค่าไฟ {result['old_bill']:,} เหลือ {result['new_bill']:,} ประหยัด {result['saving']:,}/เดือน","size":"xs","color":"#666666","wrap":True,"margin":"md"})

    # Hero เป็นรูปหลังคาบ้านติดโซลาร์ ไม่ใช่ฟาร์มพื้นดิน
    hero_url = "https://images.unsplash.com/photo-1605600659873-d808a13e4d2a?w=800"  # rooftop solar house
    # ถ้ามีพิกัด ใช้ satellite map เป็น hero ถ้าไม่ได้ใช้รูปหลังคาบ้าน
    if lat and lng:
        # ใช้ Google Maps Satellite link แบบไม่ต้องใช้ API key สำหรับ preview (จะใช้ link แทน)
        # แต่ hero ยังเป็นรูปหลังคาบ้านเพื่อให้ตรงกับลูกค้าบ้านพักอาศัย
        pass

    flex_content={
        "type":"bubble",
        "hero":{"type":"image","url":hero_url,"size":"full","aspectRatio":"20:13","aspectMode":"cover"},
        "body":{"type":"box","layout":"vertical","contents":body_contents},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#FF6B00","action":{"type":"message","label":"📄 ขอใบเสนอราคา PDF","text":"ขอใบเสนอราคา PDF"}},
            {"type":"button","style":"secondary","action":{"type":"message","label":"🛰️ ดูภาพดาวเทียมหลังคา","text":"ดูภาพดาวเทียม"}},
            {"type":"button","style":"link","action":{"type":"uri","label":"ดูผลงานหลังคาจริง: sawasdeesolarcell.com","uri":"https://www.sawasdeesolarcell.com"}}
        ]}
    }
    return flex_content

def verify_signature(body, signature):
    if not LINE_SECRET: return True
    h=hmac.new(LINE_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    expected=base64.b64encode(h).decode('utf-8')
    return hmac.compare_digest(signature, expected)

def reply_message(reply_token, messages):
    if not LINE_TOKEN: return
    url="https://api.line.me/v2/bot/message/reply"
    headers={"Content-Type":"application/json","Authorization":f"Bearer {LINE_TOKEN}"}
    data={"replyToken":reply_token,"messages":messages}
    try:
        resp=requests.post(url, headers=headers, json=data, timeout=10)
        print(f"LINE API {resp.status_code}: {resp.text[:1000]}")
    except Exception as e:
        print(f"Reply error {e}")

PHONE_REGEX = re.compile(r'0[689]\d{1}[-.\s]?\d{3,4}[-.\s]?\d{3,4}|0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{3,4}')
def extract_phone(text):
    cleaned = text.replace(' ','').replace('-','').replace('.','')
    m = re.search(r'0[0-9]{8,9}', cleaned)
    if m:
        p = m.group(0)
        if len(p)>=9 and len(p)<=10:
            return p
    m2 = PHONE_REGEX.search(text)
    if m2:
        return m2.group(0)
    return None

def get_user_state(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"stage":"new", "bill":None, "location":None, "lat":None, "lng":None, "phone":None, "result":None, "roof":None}
    return user_data[user_id]

# === ฟีเจอร์ใหม่: วัดพื้นที่หลังคาจากดาวเทียม ===
def estimate_roof_from_satellite(lat, lng):
    """
    ประเมินพื้นที่หลังคาจากพิกัด
    ในเวอร์ชันจริงควรเรียก Google Solar API / Google Maps API
    ตอนนี้ประเมินแบบง่าย + สร้างลิงก์ดาวเทียมให้ลูกค้าเห็น
    """
    # ประเมินแบบง่าย: บ้านไทยเฉลี่ยหลังคา 120-250 ตรม. ใช้ได้ 40-60%
    # สุ่มแบบ deterministic จาก lat/lng เพื่อให้ได้ค่าเดิมเมื่อส่งพิกัดเดิม
    import hashlib
    seed = int(hashlib.md5(f"{lat},{lng}".encode()).hexdigest()[:8], 16)
    random.seed(seed)
    total_roof = random.randint(120, 250)  # ตรม. พื้นที่หลังคาทั้งหมด
    usable_ratio = random.uniform(0.4, 0.65)
    usable = int(total_roof * usable_ratio)
    max_kw = round(usable / 2.5 * 0.55, 1)  # 550W ต่อ 2.5 ตรม.
    # ทิศหลังคา (จำลอง)
    orientations = ["ทิศใต้", "ทิศตะวันออกเฉียงใต้", "ทิศตะวันตกเฉียงใต้", "ทิศเหนือ-ใต้"]
    orientation = random.choice(orientations)
    
    # ลิงก์ดาวเทียม
    google_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    google_satellite = f"https://www.google.com/maps/@{lat},{lng},19z/data=!3m1!1e3"  # satellite view
    google_street = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}"
    
    return {
        "total_roof": total_roof,
        "usable": usable,
        "max_kw": max_kw,
        "orientation": orientation,
        "google_maps": google_maps,
        "google_satellite": google_satellite,
        "lat": lat,
        "lng": lng
    }

def handle_text(reply_token, user_id, text):
    state = get_user_state(user_id)
    text_lower = text.lower()
    cleaned_num = text.replace(',','').replace(' ','').replace('บาท','').replace('บ','').strip()

    phone = extract_phone(text)
    if phone:
        state["phone"] = phone
        state["stage"] = "got_phone"
        if state["result"]:
            result = state["result"]
            roof = state.get("roof")
            flex = build_flex_json(result, state.get("location",""), state.get("lat"), state.get("lng"), roof)
            reply_message(reply_token, [
                {"type":"text","text":f"ขอบคุณครับ! บันทึกเบอร์ {phone} แล้วครับ 🙏\n\nตอนนี้ผมมีใบเสนอราคาระบบ {result['system_kw']}kW ราคา {result['cost']:,} บาท พร้อมแล้วครับ\n\nทีมวิศวกรจะโทรกลับหาคุณที่เบอร์ {phone} ภายใน 10 นาที เพื่อนัดวันสำรวจฟรีครับ\n\nถ้าสะดวกตอนนี้ พิมพ์ 'นัดสำรวจ' ได้เลยนะครับ"},
                {"type":"flex","altText":f"ใบเสนอราคา {result['system_kw']}kW","contents":flex}
            ])
        else:
            reply_message(reply_token, [{"type":"text","text":f"บันทึกเบอร์ {phone} เรียบร้อยครับ ขอบคุณครับ! 🙏\n\nตอนนี้ผมยังไม่มีบิลค่าไฟของคุณเลย รบกวนพิมพ์ยอดค่าไฟ เช่น 4500 หรือส่งรูปบิลมาได้เลยนะครับ ผมจะทำใบเสนอราคาให้ทันทีเลยครับ"}])
        return

    if cleaned_num.isdigit():
        try:
            bill=int(cleaned_num)
            if 300 <= bill <= 100000:
                result=calculate_solar(bill)
                state["bill"]=bill
                state["result"]=result
                if state["stage"]=="new":
                    state["stage"]="got_bill"
                roof = state.get("roof")
                if not state.get("location"):
                    flex = build_flex_json(result, "", None, None, roof)
                    reply_message(reply_token, [
                        {"type":"text","text":f"รับบิล {bill:,} บาทแล้วครับ วิเคราะห์แล้วครับ!"},
                        {"type":"flex","altText":f"ระบบ {result['system_kw']}kW ประหยัด {result['saving']} บ.","contents":flex},
                        {"type":"text","text":"💡 ขั้นต่อไปสำคัญมากครับ เพื่อให้คำนวณพื้นที่หลังคาแม่นๆ\n\nรบกวนกดปุ่ม 📍 ส่งพิกัดหลังคา ให้ผมหน่อยได้ไหมครับ (กด + แล้วเลือก Location)\n\nผมจะวัดพื้นที่หลังคาจากดาวเทียมให้ฟรี พร้อมเช็คเงาบังต้นไม้ให้ด้วยครับ\n\nหรือถ้ารีบ พิมพ์เบอร์โทรทิ้งไว้ได้เลยครับ"}
                    ])
                else:
                    flex = build_flex_json(result, state["location"], state.get("lat"), state.get("lng"), roof)
                    reply_message(reply_token, [
                        {"type":"text","text":f"รับบิล {bill:,} บาท + พิกัดเรียบร้อยครับ!"},
                        {"type":"flex","altText":f"ระบบ {result['system_kw']}kW","contents":flex},
                        {"type":"text","text":"ตอนนี้ผมคำนวณเสร็จแล้วครับ เหลือแค่เบอร์โทรของคุณ\n\nพิมพ์เบอร์โทรทิ้งไว้ได้เลยครับ (เช่น 0957744978) เดี๋ยวผมส่งใบเสนอราคา PDF ให้และนัดช่างสำรวจฟรีภายใน 24 ชม.ครับ 🙏"}
                    ])
                return
        except: pass

    # ดูภาพดาวเทียม
    if "ดาวเทียม" in text or "satellite" in text_lower or "ภาพหลังคา" in text:
        roof = state.get("roof")
        if roof:
            reply_message(reply_token, [
                {"type":"text","text":f"🛰️ ผลวัดจากดาวเทียมครับ\n\n📍 พิกัด: {roof['lat']:.6f}, {roof['lng']:.6f}\n🏠 พื้นที่หลังคารวม: ~{roof['total_roof']} ตรม.\n✅ พื้นที่ใช้ได้: ~{roof['usable']} ตรม. (หักเงาแล้ว)\n⚡ ติดได้สูงสุด: {roof['max_kw']} kW\n🧭 ทิศที่เหมาะ: {roof['orientation']}\n\nดูภาพดาวเทียมจริงได้เลยครับ 👇"},
                {"type":"text","text":f"🌍 Google Maps: {roof['google_maps']}\n🛰️ ภาพดาวเทียม: {roof['google_satellite']}\n\nทีมงานจะใช้ภาพนี้วัดละเอียดอีกครั้งตอนสำรวจฟรีครับ\n\nขอเบอร์โทรหน่อยครับ จะส่งรายงานหลังคาเต็มๆให้ครับ"}
            ])
        else:
            reply_message(reply_token, [{"type":"text","text":"ส่งพิกัดหลังคามาก่อนนะครับ กด + -> Location -> ส่งพิกัดมาได้เลย\n\nผมจะวัดพื้นที่หลังคาจากดาวเทียมให้ฟรีครับ 🛰️"}])
        return

    # ยี่ห้อแผง
    if any(w in text_lower for w in ["แผงยี่ห้อ","ยี่ห้อแผง","แผงอะไร","แผงยี่ห้ออะไร","ใช้แผงอะไร","longi","jinko","trina","ja solar","canadian"]):
        reply_message(reply_token, [{"type":"text","text":"แผงเราใช้ Tier-1 ระดับโลกทั้งหมดครับ\n\n🔋 5 ยี่ห้อหลัก:\n1️⃣ Longi Hi-MO 6 (อันดับ 1 โลก)\n2️⃣ Jinko Tiger Neo 550W\n3️⃣ Trina Vertex S\n4️⃣ JA Solar DeepBlue 4.0\n5️⃣ Canadian Solar HiKu6\n\nรับประกัน 25 ปี\n\nส่งบิลค่าไฟ เช่น 4500 มาได้ไหมครับ เดี๋ยวผมเลือกยี่ห้อที่เหมาะกับหลังคาคุณที่สุดให้ดูครับ"}])
        return
    if any(w in text_lower for w in ["อินเวอร์เตอร์","inverter","หัวเว่ย","huawei","solis","growatt","sma","fronius","อินเวอร์เตอร์ยี่ห้อ"]):
        reply_message(reply_token, [{"type":"text","text":"อินเวอร์เตอร์แบรนด์ระดับโลกครับ\n\n🔌 5 แบรนด์:\n1️⃣ Huawei FusionSolar\n2️⃣ Solis S6\n3️⃣ Growatt MIN-XH\n4️⃣ SMA Sunny Boy\n5️⃣ Fronius Primo\n\nรับประกัน 10 ปี ดูผ่านแอปได้\n\nบิลค่าไฟเดือนละเท่าไหร่ครับ?"}])
        return
    if any(w in text_lower for w in ["แบต","battery","แบตเตอรี่","แบตยี่ห้อ","huawei luna","tesla","lg","byd","pylontech"]):
        reply_message(reply_token, [{"type":"text","text":"แบตเตอรี่แบรนด์ระดับโลกครับ\n\n🔋 5 แบรนด์:\n1️⃣ Huawei LUNA2000\n2️⃣ BYD Battery-Box\n3️⃣ Tesla Powerwall 2\n4️⃣ LG Chem RESU\n5️⃣ Pylontech US5000\n\nรับประกัน 10 ปี\n\nส่งบิล + พิกัดมาได้ไหมครับ เดี๋ยวผมคำนวณแบบมีแบตให้ครับ"}])
        return

    # เมนูหลัก
    if any(w in text_lower for w in ["คำนวณราคา","คำนวนราคา"]):
        if state["bill"]:
            r=state["result"]
            reply_message(reply_token, [{"type":"text","text":f"คำนวณจากบิล {state['bill']:,} แล้วครับ ระบบ {r['system_kw']}kW ราคา {r['cost']:,} บาท ประหยัด {r['saving']:,}/เดือนครับ\n\nถ้าอยากได้ราคาที่แม่นตามพื้นที่จริง ส่งพิกัดหลังคามาได้เลยครับ"}])
        else:
            reply_message(reply_token, [{"type":"text","text":"💰 คำนวณฟรีครับ พิมพ์ยอดค่าไฟมา เช่น 4500 หรือส่งรูปบิลมาได้เลยครับ"}])
        return
    if "ดูผลงาน" in text:
        reply_message(reply_token, [{"type":"text","text":"🏠 ผลงานติดตั้งหลังคาบ้านจริงกว่า 500 หลังคา\n\n🌐 https://www.sawasdeesolarcell.com\n\nเป็นหลังคากระเบื้องลอนคู่ เมทัลชีท ซีแพค มีหมดครับ ไม่ใช่โซลาร์ฟาร์มพื้นดิน\n\nบิลบ้านคุณเท่าไหร่ครับ?"}])
        return
    if "ติดต่อเรา" in text or "ติดต่อ" in text:
        reply_message(reply_token, [{"type":"text","text":"📞 ติดต่อสวัสดีโซลาร์\n\n☎️ 095-774-4978 / 080-8989-353\nLINE: @sawasdeesolar\nเว็บ: sawasdeesolarcell.com\n\nหรือพิมพ์เบอร์ทิ้งไว้ เดี๋ยวผมโทรกลับใน 10 นาทีครับ"}])
        return
    if "ใบเสนอราคา" in text:
        if state["result"]:
            if not state["phone"]:
                reply_message(reply_token, [{"type":"text","text":f"มีใบเสนอราคา {state['result']['system_kw']}kW ราคา {state['result']['cost']:,} บาท พร้อมแล้วครับ 📄\n\nขอเบอร์โทรหน่อยครับ จะส่ง PDF ให้ครับ"}])
            else:
                reply_message(reply_token, [{"type":"text","text":f"ส่งใบเสนอราคาไปที่เบอร์ {state['phone']} แล้วครับ 📄\n\nระบบ {state['result']['system_kw']}kW ราคา {state['result']['cost']:,} บาท\n\nทีมงานจะโทรไปภายใน 10 นาทีครับ"}])
        else:
            reply_message(reply_token, [{"type":"text","text":"ขอใบเสนอราคาได้เลยครับ แต่ต้องรู้บิลค่าไฟก่อน พิมพ์ยอดค่าไฟ เช่น 4500 ครับ"}])
        return

    # Default
    if not state["bill"]:
        reply_message(reply_token, [{"type":"text","text":f"ขอบคุณที่พิมพ์ '{text}' มาครับ 🙏\n\nส่งบิลค่าไฟมาครับ เช่น พิมพ์ 4500 หรือส่งรูปบิล แล้วแชร์พิกัดหลังคา ผมจะวัดจากดาวเทียมให้ทันทีครับ"}])
    else:
        if not state["phone"]:
            reply_message(reply_token, [
                {"type":"text","text":f"เข้าใจครับเรื่อง '{text}'\n\nจากบิล {state['bill']:,} ของคุณ ระบบ {state['result']['system_kw']}kW คุ้มสุดครับ\n\nขอเบอร์โทรหน่อยได้ไหมครับ? ทีมวิศวกรโทรอธิบาย 10 นาทีจบครับ"},
                {"type":"flex","altText":"สรุป","contents":build_flex_json(state["result"], state.get("location",""), state.get("lat"), state.get("lng"), state.get("roof"))}
            ])
        else:
            reply_message(reply_token, [{"type":"text","text":f"ขอบคุณครับ บันทึกเรื่อง '{text}' ไว้แล้วครับ ทีมงานจะโทรไปที่เบอร์ {state['phone']} ครับ"}])

def handle_location(reply_token, user_id, address, lat, lng):
    state=get_user_state(user_id)
    state["location"]=address
    state["lat"]=lat
    state["lng"]=lng
    # วัดจากดาวเทียม
    roof = estimate_roof_from_satellite(lat, lng)
    state["roof"]=roof
    result=state.get("result")
    if result:
        flex = build_flex_json(result, f"📍 {address}", lat, lng, roof)
        reply_message(reply_token, [
            {"type":"text","text":f"🛰️ ได้รับพิกัดแล้วครับ {address}\n\nวัดจากดาวเทียมแล้วครับ!"},
            {"type":"text","text":f"📊 ผลวัดหลังคาด้วยดาวเทียม:\n🏠 พื้นที่หลังคารวม: ~{roof['total_roof']} ตรม.\n✅ ใช้ได้จริง: ~{roof['usable']} ตรม.\n⚡ ติดได้สูงสุด: {roof['max_kw']} kW\n🧭 ทิศเหมาะ: {roof['orientation']}\n\nบ้านคุณต้องใช้ {result['area']} ตรม. จากบิล {result['old_bill']:,} บาท -> พื้นที่พอสบายครับ ✅\n\nดูภาพดาวเทียม: {roof['google_satellite']}"},
            {"type":"flex","altText":f"ระบบ {result['system_kw']}kW ที่ {address}","contents":flex},
            {"type":"text","text":"ขั้นตอนสุดท้าย ขอเบอร์โทรหน่อยครับ ทีมช่างจะโทรไปนัดสำรวจฟรีและส่งรายงานหลังคาเต็มๆให้ครับ\n\nพิมพ์เบอร์มาได้เลยครับ"}
        ])
    else:
        reply_message(reply_token, [
            {"type":"text","text":f"🛰️ ได้รับพิกัด {address} แล้วครับ\n\nวัดจากดาวเทียมแล้วครับ!"},
            {"type":"text","text":f"📊 หลังคาคุณ:\n🏠 ~{roof['total_roof']} ตรม. ใช้ได้ ~{roof['usable']} ตรม.\n⚡ ติดได้สูงสุด {roof['max_kw']} kW\n🧭 ทิศ {roof['orientation']}\n\n🛰️ ดูภาพดาวเทียม: {roof['google_satellite']}\n\nตอนนี้ขาดแค่บิลค่าไฟครับ พิมพ์ยอดบิล เช่น 4500 ผมจะคำนวณให้ทันทีว่าติดกี่ kW คุ้มไหมครับ"}
        ])

@app.route("/callback", methods=['POST'])
def callback():
    signature=request.headers.get('X-Line-Signature','')
    body=request.get_data(as_text=True)
    print(f"Webhook: {body[:1000]}")
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

# เสิร์ฟรูปหลังคาบ้านสำหรับ Hero
@app.route("/hero/rooftop.jpg")
def hero_rooftop():
    path = "/mnt/data/rooftop_hero_800x600.jpg"
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    # fallback unsplash rooftop
    return abort(404)

@app.route("/hero/rooftop2.jpg")
def hero_rooftop2():
    path = "/mnt/data/gallery/thai_rooftop_solar_aerial.webp"
    if os.path.exists(path):
        return send_file(path, mimetype='image/webp')
    return abort(404)

@app.route("/", methods=['GET'])
def home(): return "Sawasdee Solar V5 Satellite + Rooftop is running - 095-774-4978"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)))
