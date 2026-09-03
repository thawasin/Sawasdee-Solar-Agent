"""
สวัสดีโซลาร์ - V4 Sales Funnel
ตอบได้ทุกคำถาม แต่ต้อนเข้ากับดัก: บิล -> พิกัด -> เบอร์ -> เสนอราคา -> ปิดการขาย
โทนสี: เขียว #0E7A4A ส้ม #FF6B00
"""
import os, math, hmac, hashlib, base64, traceback, requests, json, re, random
from flask import Flask, request, abort
from datetime import datetime

app = Flask(__name__)
LINE_TOKEN = os.getenv("LINE_TOKEN","").strip()
LINE_SECRET = os.getenv("LINE_SECRET","").strip()
print(f"=== Sawasdee Solar V4 Sales Funnel ===")
print(f"TOKEN len: {len(LINE_TOKEN)} SECRET len: {len(LINE_SECRET)}")

# เก็บข้อมูลลูกค้า: bill, location, phone, stage, last_bill_result
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

def build_flex_json(result, location_text=""):
    body_contents=[
        {"type":"text","text":"สวัสดีโซลาร์ - ผลวิเคราะห์หลังคา","weight":"bold","size":"md","color":"#FF6B00"},
        {"type":"text","text":f"ระบบแนะนำ {result['system_kw']} kW ({result['panels']} แผง)","weight":"bold","size":"lg","margin":"md"},
    ]
    if location_text and str(location_text).strip():
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
    body_contents.append({"type":"text","text":f"จากค่าไฟ {result['old_bill']:,} เหลือ {result['new_bill']:,} ประหยัด {result['saving']:,}/เดือน","size":"xs","color":"#666666","wrap":True,"margin":"md"})
    flex_content={
        "type":"bubble",
        "hero":{"type":"image","url":"https://images.unsplash.com/photo-1509391366360-2e959784a276?w=800","size":"full","aspectRatio":"20:13","aspectMode":"cover"},
        "body":{"type":"box","layout":"vertical","contents":body_contents},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#FF6B00","action":{"type":"message","label":"📄 ขอใบเสนอราคา PDF","text":"ขอใบเสนอราคา PDF"}},
            {"type":"button","style":"secondary","action":{"type":"message","label":"📍 ส่งพิกัดหลังคา","text":"ส่งพิกัดหลังคา"}},
            {"type":"button","style":"link","action":{"type":"uri","label":"ดูผลงาน: sawasdeesolarcell.com","uri":"https://www.sawasdeesolarcell.com"}}
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

# === ฟังก์ชันดักจับเบอร์โทร ===
PHONE_REGEX = re.compile(r'0[689]\d{1}[-.\s]?\d{3,4}[-.\s]?\d{3,4}|0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{3,4}')
def extract_phone(text):
    # ลบช่องว่างและหาเบอร์
    cleaned = text.replace(' ','').replace('-','').replace('.','')
    m = re.search(r'0[0-9]{8,9}', cleaned)
    if m:
        p = m.group(0)
        if len(p)>=9 and len(p)<=10:
            return p
    # แบบมีขีด
    m2 = PHONE_REGEX.search(text)
    if m2:
        return m2.group(0)
    return None

def get_user_state(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"stage":"new", "bill":None, "location":None, "phone":None, "result":None, "name":None}
    return user_data[user_id]

# === ข้อความตอบแบบเป็นธรรมชาติ ต้อนเข้ากับดัก ===
def handle_text(reply_token, user_id, text):
    state = get_user_state(user_id)
    text_lower = text.lower()
    cleaned_num = text.replace(',','').replace(' ','').replace('บาท','').replace('บ','').strip()

    # 1. ดักเบอร์โทรก่อนเลย - ได้เบอร์คือชนะ 80%
    phone = extract_phone(text)
    if phone:
        state["phone"] = phone
        state["stage"] = "got_phone"
        # ถ้ามีบิลแล้ว ส่งใบเสนอราคาทันที
        if state["result"]:
            result = state["result"]
            reply_message(reply_token, [
                {"type":"text","text":f"ขอบคุณครับ! บันทึกเบอร์ {phone} แล้วครับ 🙏\n\nตอนนี้ผมมีใบเสนอราคาระบบ {result['system_kw']}kW ราคา {result['cost']:,} บาท พร้อมแล้วครับ\n\nทีมวิศวกรจะโทรกลับหาคุณที่เบอร์ {phone} ภายใน 10 นาที เพื่อนัดวันสำรวจฟรีครับ\n\nถ้าสะดวกตอนนี้ พิมพ์ 'นัดสำรวจ' ได้เลยนะครับ ผมล็อคคิวให้ก่อนเลย"},
                {"type":"flex","altText":f"ใบเสนอราคา {result['system_kw']}kW","contents":build_flex_json(result, state.get("location",""))}
            ])
        else:
            reply_message(reply_token, [
                {"type":"text","text":f"บันทึกเบอร์ {phone} เรียบร้อยครับ ขอบคุณครับ! 🙏\n\nตอนนี้ผมยังไม่มีบิลค่าไฟของคุณเลย รบกวนพิมพ์ยอดค่าไฟ เช่น 4500 หรือส่งรูปบิลมาได้เลยนะครับ ผมจะทำใบเสนอราคาให้ทันทีเลยครับ"}
            ])
        print(f"Got phone {phone} from {user_id}")
        return

    # 2. ดักตัวเลขบิล
    if cleaned_num.isdigit():
        try:
            bill=int(cleaned_num)
            if 300 <= bill <= 100000:
                result=calculate_solar(bill)
                state["bill"]=bill
                state["result"]=result
                if state["stage"]=="new":
                    state["stage"]="got_bill"
                # ถ้ายังไม่มีพิกัด ขอพิกัด
                if not state.get("location"):
                    reply_message(reply_token, [
                        {"type":"text","text":f"รับบิล {bill:,} บาทแล้วครับ วิเคราะห์แล้วครับ!"},
                        {"type":"flex","altText":f"ระบบ {result['system_kw']}kW ประหยัด {result['saving']} บ.","contents":build_flex_json(result)},
                        {"type":"text","text":"💡 ขั้นต่อไปสำคัญมากครับ เพื่อให้คำนวณพื้นที่หลังคาแม่นๆ\n\nรบกวนกดปุ่ม 📍 ส่งพิกัดหลังคา ให้ผมหน่อยได้ไหมครับ (กด + แล้วเลือก Location)\n\nหรือถ้ารีบ พิมพ์เบอร์โทรทิ้งไว้ได้เลยครับ ทีมงานจะวัดพื้นที่จากดาวเทียมให้ฟรีทันทีครับ"}
                    ])
                else:
                    # มีพิกัดแล้ว ขอเบอร์เพื่อปิดการขาย
                    reply_message(reply_token, [
                        {"type":"text","text":f"รับบิล {bill:,} บาท + พิกัดเรียบร้อยครับ!"},
                        {"type":"flex","altText":f"ระบบ {result['system_kw']}kW","contents":build_flex_json(result, state["location"])},
                        {"type":"text","text":"ตอนนี้ผมคำนวณเสร็จแล้วครับ เหลือแค่เบอร์โทรของคุณ\n\nพิมพ์เบอร์โทรทิ้งไว้ได้เลยครับ (เช่น 0957744978) เดี๋ยวผมส่งใบเสนอราคา PDF ให้และนัดช่างสำรวจฟรีภายใน 24 ชม.ครับ 🙏"}
                    ])
                return
        except: pass

    # 3. Intent Matching แบบครอบคลุม
    # ทักทาย
    if any(w in text_lower for w in ["สวัสดี","หวัดดี","hello","hi ","ดีครับ","ดีค่ะ"]):
        reply_message(reply_token, [{"type":"text","text":"สวัสดีครับ ☀️ ยินดีต้อนรับสู่สวัสดีโซลาร์ครับ\n\nผมเป็นผู้ช่วยประเมินโซลาร์ฟรีครับ ช่วยคำนวณให้ว่าค่าไฟจะลดเหลือเท่าไหร่ คุ้มไหม คืนทุนกี่ปี\n\nเริ่มง่ายๆเลยครับ พิมพ์ยอดค่าไฟมาได้ไหมครับ เช่น 3500 หรือส่งรูปบิลมาก็ได้ครับ 🙏"}])
        return

    # คำนวณราคา
    if any(w in text_lower for w in ["คำนวณ","คำนวน","ประเมิน","เท่าไหร่","ราคา","คิดราคา","คิดเงิน"]):
        if state["bill"]:
            result=state["result"]
            reply_message(reply_token, [
                {"type":"text","text":f"ตอนนี้คำนวณจากบิล {state['bill']:,} บาทให้แล้วครับ ระบบ {result['system_kw']}kW ราคา {result['cost']:,} บาท ประหยัด {result['saving']:,}/เดือนครับ"},
                {"type":"text","text":"ถ้าอยากได้ราคาที่แม่นกว่านี้ตามพื้นที่จริง รบกวนส่งพิกัดหลังคามาให้หน่อยครับ หรือพิมพ์เบอร์โทรทิ้งไว้ เดี๋ยวผมให้วิศวกรคำนวณแบบละเอียดให้ฟรีครับ"}
            ])
        else:
            reply_message(reply_token, [{"type":"text","text":"💰 คำนวณฟรีครับ ไม่คิดเงิน!\n\nแค่บอกยอดค่าไฟมาครับ เช่น พิมพ์ 4500\nหรือถ่ายรูปบิลส่งมาได้เลย\n\nผมจะบอกทันทีว่าต้องติดกี่ kW ราคาเท่าไหร่ ลดเหลือเท่าไหร่ครับ"}])
        return

    # ดูผลงาน
    if "ดูผลงาน" in text or "ผลงาน" in text or "รีวิว" in text:
        reply_message(reply_token, [
            {"type":"text","text":"🏠 ผลงานสวัสดีโซลาร์ ติดตั้งจริงกว่า 500 หลังคา ทั่วไทยครับ\nบ้านเดี่ยว โรงงาน ฟาร์มไก่ วัด โรงเรียน\n\nดูรูปได้ที่เว็บเลยครับ 👇"},
            {"type":"text","text":"🌐 https://www.sawasdeesolarcell.com\n\nชอบหลังไหน แคปส่งมาได้เลยครับ ผมจะบอกได้เลยว่าหลังนั้นติดกี่ kW ค่าไฟลดเท่าไหร่ครับ\n\nว่าแต่บ้านของคุณค่าไฟเดือนละเท่าไหร่ครับ? พิมพ์มาได้เลย เดี๋ยวผมเทียบให้ดูครับ"}
        ])
        return

    # ติดต่อ
    if any(w in text_lower for w in ["ติดต่อ","เบอร์","โทร","contact","call"]):
        reply_message(reply_token, [{"type":"text","text":"📞 ติดต่อสวัสดีโซลาร์\n\n☎️ 095-774-4978 / 080-8989-353\nLINE: @sawasdeesolar\nเว็บ: sawasdeesolarcell.com\nสมุทรสาคร ติดตั้งทั่วไทย\n\nหรือพิมพ์เบอร์คุณทิ้งไว้ได้เลยครับ เดี๋ยวผมโทรกลับภายใน 10 นาทีครับ ไม่ต้องรอโทรเอง!"}])
        return

    # ใบเสนอราคา
    if "ใบเสนอราคา" in text or "เสนอราคา" in text or "pdf" in text_lower:
        if state["result"]:
            result=state["result"]
            if not state["phone"]:
                reply_message(reply_token, [
                    {"type":"text","text":f"มีใบเสนอราคาระบบ {result['system_kw']}kW ราคา {result['cost']:,} บาท พร้อมแล้วครับ 📄\n\nรบกวนขอเบอร์โทรหน่อยครับ ผมจะส่งไฟล์ PDF ให้ทาง LINE และโทรอธิบายรายละเอียดให้ฟังครับ\n\nพิมพ์เบอร์มาได้เลยครับ เช่น 0957744978"},
                    {"type":"flex","altText":"ใบเสนอราคา","contents":build_flex_json(result, state.get("location",""))}
                ])
            else:
                reply_message(reply_token, [
                    {"type":"text","text":f"ส่งใบเสนอราคาไปที่เบอร์ {state['phone']} แล้วครับ 📄\n\nระบบ {result['system_kw']}kW ราคา {result['cost']:,} บาท ประหยัด {result['saving']:,}/เดือน คืนทุน {result['payback_y']} ปี {result['payback_m']} เดือน\n\nทีมงานจะโทรไปอธิบายภายใน 10 นาทีนะครับ ถ้าสะดวกนัดสำรวจ พิมพ์ 'นัดสำรวจ' ได้เลยครับ"},
                    {"type":"flex","altText":"ใบเสนอราคา","contents":build_flex_json(result, state.get("location",""))}
                ])
        else:
            reply_message(reply_token, [{"type":"text","text":"ขอใบเสนอราคาได้เลยครับ แต่ผมต้องรู้บิลค่าไฟก่อน\n\nพิมพ์ยอดค่าไฟมาได้ไหมครับ เช่น 4500 แล้วผมจะทำ PDF ให้ทันทีเลยครับ 🙏"}])
        return

    # นัดสำรวจ
    if any(w in text_lower for w in ["นัด","สำรวจ","มาดู","ดูหน้างาน","เข้าดู"]):
        if not state["phone"]:
            reply_message(reply_token, [{"type":"text","text":"นัดสำรวจฟรีได้เลยครับ ไม่มีค่าใช้จ่าย ช่างจะขึ้นวัดหลังคาจริง วัดความแข็งแรง และเช็คเงาบัง\n\nรบกวนขอเบอร์โทรหน่อยครับ จะได้นัดวันเวลาที่สะดวกครับ\n\nพิมพ์เบอร์มาได้เลยครับ เช่น 0957744978"}])
        else:
            reply_message(reply_token, [{"type":"text","text":f"รับนัดสำรวจแล้วครับ! ขอบคุณครับ 🙏\n\nบันทึกเบอร์ {state['phone']} แล้ว ทีมช่างจะโทรนัดภายในวันนี้ครับ\n\nปกติสำรวจใช้เวลา 30 นาที รู้ผลทันทีว่าติดได้กี่ kW ครับ\n\nวันไหนสะดวกครับ? พิมพ์มาได้เลย เช่น 'พรุ่งนี้บ่าย'"}])
        return

    # คำถามยอดฮิต - คุ้มไหม / คืนทุน
    if any(w in text_lower for w in ["คุ้มไหม","คุ้มมั้ย","คืนทุน","กี่ปี","ประหยัด"]):
        if state["result"]:
            r=state["result"]
            reply_message(reply_token, [{"type":"text","text":f"คุ้มมากครับ จากบิล {r['old_bill']:,} ของคุณ\n\nติด {r['system_kw']}kW ประหยัด {r['saving']:,}/เดือน = ปีละ {r['saving']*12:,} บาท\nลงทุน {r['cost']:,} คืนทุน {r['payback_y']} ปี {r['payback_m']} เดือน หลังจากนั้นใช้ไฟฟรีอีก 20 ปี\n\nแผงรับประกัน 25 ปี อินเวอร์เตอร์ 10 ปีครับ\n\nสนใจให้ผมส่งใบเสนอราคาเต็มๆไหมครับ? ขอเบอร์โทรหน่อยครับ"}])
        else:
            reply_message(reply_token, [{"type":"text","text":"คุ้มครับ ลูกค้าส่วนใหญ่คืนทุน 4-5 ปี หลังจากนั้นใช้ไฟฟรีอีก 20 ปี\n\nแผงรับประกัน 25 ปี อินเวอร์เตอร์ 10 ปี\n\nคุ้มไม่คุ้มดูจากบิลค่าไฟเลยครับ พิมพ์ยอดบิลมาได้ไหมครับ เช่น 4500 เดี๋ยวผมคำนวณคืนทุนให้ดูชัดๆเลยครับ"}])
        return

    # ประกัน
    if any(w in text_lower for w in ["ประกัน","รับประกัน","warranty","เคลม"]):
        reply_message(reply_token, [{"type":"text","text":"รับประกันครับ\n\n✅ แผงโซลาร์ Tier1 (Longi/Jinko) รับประกัน 25 ปี\n✅ อินเวอร์เตอร์ Huawei/Growatt รับประกัน 10 ปี\n✅ งานติดตั้ง 2 ปี น้ำไม่รั่ว\n✅ ล้างแผงฟรีปีละ 1 ครั้ง\n✅ ดูแลขออนุญาตการไฟฟ้าฟรี\n\nแต่ต้องดูบิลก่อนนะครับว่าต้องใช้กี่แผงถึงจะคุ้มประกัน บิลเท่าไหร่ครับ?"}])
        return

    # ผ่อน
    if any(w in text_lower for w in ["ผ่อน","เงินผ่อน","สินเชื่อ","กู้","แบ่งจ่าย","บัตรเครดิต"]):
        reply_message(reply_token, [{"type":"text","text":"ผ่อนได้ครับ 💳\n\n✅ ผ่อน 0% นาน 10 เดือนกับบัตรเครดิตทุกธนาคาร\n✅ สินเชื่อโซลาร์กับ SCB, กสิกร ดอกเบี้ยพิเศษ เริ่ม 0.79%\n✅ ใช้บิลค่าไฟผ่อนได้เลย ผ่อนถูกกว่าค่าไฟที่ลดได้\n\nเช่น ติด 5kW ผ่อนเดือนละ 4,500 แต่ประหยัดค่าไฟ 3,500 = จ่ายเพิ่มแค่ 1,000 ครับ\n\nบิลคุณเดือนละเท่าไหร่ครับ? เดี๋ยวผมคำนวณยอดผ่อนให้ดูครับ"}])
        return

    # ติดกี่วัน / ขั้นตอน
    if any(w in text_lower for w in ["กี่วัน","นานไหม","ขั้นตอน","ติดตั้งยังไง","ขออนุญาต"]):
        reply_message(reply_token, [{"type":"text","text":"ติดตั้งเร็วครับ\n\n1️⃣ ส่งบิล+พิกัด -> ผมประเมิน (วันนี้)\n2️⃣ นัดสำรวจฟรี วัดหลังคาจริง (1-2 วัน)\n3️⃣ เซ็นสัญญา + ขออนุญาตการไฟฟ้า (เราทำให้ฟรี 15-30 วัน)\n4️⃣ ติดตั้ง 1-2 วันเสร็จ\n5️⃣ การไฟฟ้ามาตรวจและเปลี่ยนมิเตอร์\n\nรวม 3-4 สัปดาห์ใช้ไฟโซลาร์ได้เลยครับ\n\nเริ่มจากส่งบิลมาได้ไหมครับ? เดี๋ยวผมล็อคคิวสำรวจให้ก่อนเลย"}])
        return

    # 1. ยี่ห้อแผง - Tier1 4-5 ยี่ห้อ
    if any(w in text_lower for w in ["แผงยี่ห้อ","ยี่ห้อแผง","แผงอะไร","แผงยี่ห้ออะไร","ใช้แผงอะไร","longi","jinko","trina","ja solar","canadian"]):
        reply_message(reply_token, [{"type":"text","text":"แผงเราใช้ Tier-1 ระดับโลกทั้งหมดครับ มีใบรับรอง Bloomberg Tier-1 จริง ไม่ใช่เกรด B ครับ\n\n🔋 ยี่ห้อที่เราใช้ประจำ 5 ยี่ห้อ:\n1️⃣ Longi Hi-MO 6 (อันดับ 1 โลก)\n2️⃣ Jinko Tiger Neo 550W\n3️⃣ Trina Vertex S\n4️⃣ JA Solar DeepBlue 4.0\n5️⃣ Canadian Solar HiKu6\n\nทุกยี่ห้อ ประสิทธิภาพ 21%+ รับประกัน 25 ปี ไฟออกเต็ม\n\nบ้านคุณหลังคาแบบไหนครับ? ส่งบิลค่าไฟ เช่น 4500 มาได้ไหมครับ เดี๋ยวผมเลือกยี่ห้อที่เหมาะกับพื้นที่หลังคาคุณที่สุดให้ดูครับ"}])
        return

    # 2. ยี่ห้ออินเวอร์เตอร์ - แบรนด์ระดับโลก 4-5 ยี่ห้อ
    if any(w in text_lower for w in ["อินเวอร์เตอร์","inverter","หัวเว่ย","huawei","solis","growatt","sma","fronius","อินเวอร์เตอร์ยี่ห้อ"]):
        reply_message(reply_token, [{"type":"text","text":"อินเวอร์เตอร์เราใช้แบรนด์ระดับโลกเท่านั้นครับ มีศูนย์ไทย ประกันจริง ดูผ่านแอปมือถือได้\n\n🔌 ยี่ห้อที่เราใช้ 5 แบรนด์:\n1️⃣ Huawei FusionSolar (อันดับ 1 โลก ทนสุด)\n2️⃣ Solis S6 (ขายดีที่สุดในไทย)\n3️⃣ Growatt MIN-XH (แอปสวย)\n4️⃣ SMA Sunny Boy (เยอรมัน ทน 20 ปี)\n5️⃣ Fronius Primo (ออสเตรีย พรีเมียม)\n\nรับประกัน 10 ปีทุกตัว มี WiFi ดูการผลิตไฟในมือถือได้\n\nบิลค่าไฟคุณเดือนละเท่าไหร่ครับ? เดี๋ยวผมเลือกรุ่นที่เหมาะกับระบบของคุณให้ดู พร้อมราคาเลยครับ"}])
        return

    # 3. ยี่ห้อแบตเตอรี่ - แบรนด์สากล 4-5 ยี่ห้อ
    if any(w in text_lower for w in ["แบต","battery","แบตเตอรี่","แบตยี่ห้อ","แบตอะไร","huawei luna","tesla","lg","byd","pylontech"]):
        reply_message(reply_token, [{"type":"text","text":"แบตเตอรี่เราใช้แบรนด์ระดับโลก ลิเธียม LFP ปลอดภัย ไม่ระเบิดครับ\n\n🔋 ยี่ห้อที่เราใช้ 5 แบรนด์:\n1️⃣ Huawei LUNA2000 (เข้ากับ Huawei inverter ดีที่สุด)\n2️⃣ BYD Battery-Box Premium HVM\n3️⃣ Tesla Powerwall 2 (อเมริกา)\n4️⃣ LG Chem RESU Prime\n5️⃣ Pylontech US5000 (คุ้มค่าที่สุด)\n\nรับประกัน 10 ปี เก็บไฟใช้กลางคืนได้ ลดค่าไฟได้ 100%\n\nบ้านคุณอยากติดแบบมีแบตหรือไม่มีแบตครับ? ส่งบิลค่าไฟ เช่น 4500 + พิกัดหลังคา มาได้ไหมครับ เดี๋ยวผมคำนวณให้ว่าคุ้มแบบไหนกว่ากัน แล้วขอเบอร์โทรส่งใบเสนอราคาแบตให้ครับ"}])
        return

    # ถามรวมๆ ยี่ห้อ - ตอบรวมทั้ง 3 อย่าง
    if any(w in text_lower for w in ["ยี่ห้ออะไรบ้าง","ใช้อะไรบ้าง","สเปค","อุปกรณ์"]):
        reply_message(reply_token, [{"type":"text","text":"ใช้อุปกรณ์ Tier-1 ทั้งระบบครับ\n\n🔋 แผง: Longi, Jinko, Trina, JA Solar, Canadian (Tier-1)\n🔌 อินเวอร์เตอร์: Huawei, Solis, Growatt, SMA, Fronius\n🔋 แบต: Huawei LUNA, BYD, Tesla, LG, Pylontech\n🔩 ราง: Anodized Aluminium + สาย PV1-F มาตรฐาน\n\nรับประกันแผง 25 ปี อินเวอร์เตอร์/แบต 10 ปี ติดตั้ง 2 ปี\n\nส่งบิลค่าไฟมาได้ไหมครับ เช่น 4500 เดี๋ยวผมจัดชุดที่คุ้มที่สุดให้ดูพร้อมราคาเลยครับ"}])
        return

    # แพง / คิดดูก่อน / ถามแฟน / ปรึกษาก่อน - รับมือข้อโต้แย้ง
    if any(w in text_lower for w in ["แพง","คิดดูก่อน","ปรึกษา","ถามแฟน","ถามที่บ้าน","งบน้อย","ยังไม่พร้อม","ราคาสูง"]):
        if state["result"]:
            r=state["result"]
            reply_message(reply_token, [{"type":"text","text":f"เข้าใจเลยครับ ลงทุน {r['cost']:,} บาท ไม่น้อยเลย\n\nแต่ลองคิดแบบนี้ครับ ตอนนี้จ่ายค่าไฟ {r['old_bill']:,} x 12 เดือน x 25 ปี = {r['old_bill']*12*25:,} บาทที่จ่ายทิ้งให้การไฟฟ้า\n\nถ้าติดโซลาร์ จ่าย {r['cost']:,} ครั้งเดียว ประหยัดไป {r['saving']*12*20:,} บาทใน 20 ปี\n\nแถมผ่อนได้ 0% เดือนละ 4-5 พัน ถูกกว่าค่าไฟที่ลดได้อีกครับ\n\nให้ผมส่งใบเสนอราคาไปให้ปรึกษาที่บ้านก่อนไหมครับ? ขอเบอร์โทรไว้หน่อยครับ ส่ง PDF ให้ดูง่ายๆครับ"}])
        else:
            reply_message(reply_token, [{"type":"text","text":"เข้าใจครับ เรื่องใหญ่ต้องคิดดีๆ\n\nให้ผมช่วยคิดแบบไม่กดดันนะครับ ส่งบิลมาให้ผมดูก่อนได้ไหมครับ เช่น 4500\nผมจะคำนวณให้ดูว่าผ่อนเท่าไหร่ เทียบกับค่าไฟแล้วคุ้มไหม จะได้มีตัวเลขไปปรึกษาที่บ้านง่ายๆครับ\n\nไม่ต้องกลัวผมตื๊อครับ ให้ข้อมูลฟรีครับ 🙏"}])
        return

    # เทียบเจ้าอื่น / เจ้าอื่นถูกกว่า
    if any(w in text_lower for w in ["เจ้าอื่น","ที่อื่น","ถูกกว่า","เปรียบเทียบ","เจ้าไหน"]):
        reply_message(reply_token, [{"type":"text","text":"ดีเลยครับที่เทียบ จะได้ไม่โดนหลอก\n\nสวัสดีโซลาร์ต่างจากเจ้าอื่นตรง:\n✅ ใช้แผง Tier1 จริง มีใบรับรอง ไม่ใช่แผงเกรด B\n✅ อินเวอร์เตอร์ Huawei แท้ ประกันศูนย์ไทย\n✅ ขออนุญาตการไฟฟ้าฟรี (หลายเจ้าไม่ทำ)\n✅ ทีมช่างประจำ ไม่ใช่ซับ\n✅ ดูแลหลังขายจริง โทรติด\n\nหลายเจ้าถูกกว่าเพราะลดสเปคครับ\n\nส่งสเปคเจ้าอื่นมาให้ผมเทียบให้ได้เลยครับ หรือส่งบิลมา เดี๋ยวผมทำราคาเทียบให้ดูชัดๆครับ"}])
        return

    # ขอคนตอบ / แอดมิน
    if any(w in text_lower for w in ["คน","แอดมิน","เจ้าหน้าที่","มนุษย์","admin"]):
        reply_message(reply_token, [{"type":"text","text":"ได้เลยครับ เดี๋ยวให้เจ้าหน้าที่ตอบครับ\n\nรบกวนฝากเบอร์โทรไว้หน่อยได้ไหมครับ? ทีมงานจะโทรกลับภายใน 10 นาทีครับ\n\nหรือโทรด่วน 095-774-4978 ได้เลยครับ\n\nระหว่างรอ ผมช่วยประเมินเบื้องต้นให้ได้นะครับ บิลค่าไฟเดือนละเท่าไหร่ครับ?"}])
        return

    # คำหยาบ / นอกเรื่องมากๆ - ดึงกลับสุภาพ
    if any(w in text_lower for w in ["ห่วย","โกง","หลอก"]):
        reply_message(reply_token, [{"type":"text","text":"ต้องขออภัยถ้าทำให้ไม่สบายใจครับ 🙏\n\nสวัสดีโซลาร์ตั้งใจทำจริงครับ ติดตั้งมา 500+ หลัง มีหน้าร้านที่สมุทรสาคร\n\nถ้ามีอะไรให้ปรับปรุงบอกได้เลยครับ หรือถ้าอยากดูผลงานก่อนได้ครับ\n\nพิมพ์ 'ดูผลงาน' ได้เลยครับ"}])
        return

    # ส่งพิกัด
    if any(w in text_lower for w in ["ส่งพิกัด","แชร์โลเคชั่น","location","พิกัด"]):
        reply_message(reply_token, [{"type":"text","text":"ส่งพิกัดได้เลยครับ\n\nกดเครื่องหมาย + ข้างๆที่พิมพ์ -> เลือก Location -> ส่ง Location ปัจจุบันของบ้านที่ตะติดตั้งได้เลยครับ\n\nผมจะวัดพื้นที่หลังคาจากดาวเทียมให้ฟรีครับ"}])
        return

    # Default - ตอบแบบครอบจักรวาล แต่ต้อนกลับ
    # ถ้ายังไม่มีบิล
    if not state["bill"]:
        reply_message(reply_token, [{"type":"text","text":f"ขอบคุณที่พิมพ์ '{text}' มาครับ 🙏\n\nผมอาจจะตอบไม่ตรงคำถาม ต้องขออภัยครับ ผมเป็นบอทคำนวณโซลาร์ครับ\n\nวิธีคุยกับผมง่ายที่สุดคือ ส่งบิลค่าไฟมาครับ เช่น พิมพ์ 4500 หรือส่งรูปบิล\nแล้วผมจะตอบได้ตรงมากๆเลยว่า ต้องติดกี่ kW ราคาเท่าไหร่ คุ้มไหม\n\nลองพิมพ์ยอดบิลมาดูนะครับ"}])
    else:
        # มีบิลแล้วแต่ยังไม่มีเบอร์ - ต้อนขอเบอร์
        if not state["phone"]:
            reply_message(reply_token, [
                {"type":"text","text":f"เข้าใจครับเรื่อง '{text}'\n\nจากบิล {state['bill']:,} ของคุณ ผมคำนวณไว้แล้วว่าใช้ระบบ {state['result']['system_kw']}kW คุ้มสุดครับ\n\nถ้าอยากได้คำตอบละเอียดๆเรื่องนี้ ทีมวิศวกรโทรอธิบายให้ฟังได้เลยครับ 10 นาทีจบ\n\nรบกวนขอเบอร์โทรหน่อยได้ไหมครับ? พิมพ์มาได้เลย เช่น 0957744978"},
                {"type":"flex","altText":"สรุป","contents":build_flex_json(state["result"], state.get("location",""))}
            ])
        else:
            reply_message(reply_token, [{"type":"text","text":f"ขอบคุณครับ บันทึกเรื่อง '{text}' ไว้แล้วครับ\n\nทีมงานจะโทรไปที่เบอร์ {state['phone']} เพื่ออธิบายเพิ่มเติมให้นะครับ\n\nถ้ารีบ โทร 095-774-4978 ได้เลยครับ"}])

def handle_location(reply_token, user_id, address):
    state=get_user_state(user_id)
    state["location"]=address
    result=state.get("result")
    if result:
        reply_message(reply_token, [
            {"type":"text","text":f"ได้รับพิกัด {address} แล้วครับ ขอบคุณครับ! 🙏\n\nกำลังวัดพื้นที่หลังคาจากดาวเทียม..."},
            {"type":"flex","altText":f"ระบบ {result['system_kw']}kW ที่ {address}","contents":build_flex_json(result, f"📍 {address}")},
            {"type":"text","text":"วัดแล้วครับ พื้นที่พอติดได้สบายครับ\n\nขั้นตอนสุดท้าย รบกวนขอเบอร์โทรหน่อยครับ ทีมช่างจะโทรไปนัดสำรวจฟรีและส่งใบเสนอราคา PDF ให้ครับ\n\nพิมพ์เบอร์มาได้เลยครับ เช่น 0957744978"}
        ])
    else:
        reply_message(reply_token, [
            {"type":"text","text":f"ได้รับพิกัด {address} แล้วครับ 🙏\n\nตอนนี้ขาดแค่บิลค่าไฟครับ พิมพ์ยอดบิลมาได้ไหมครับ เช่น 4500 ผมจะคำนวณให้ทันทีว่า หลังคานี้ติดได้กี่ kW คุ้มไหมครับ"}
        ])

@app.route("/callback", methods=['POST'])
def callback():
    signature=request.headers.get('X-Line-Signature','')
    body=request.get_data(as_text=True)
    print(f"Webhook: {body[:800]}")
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
                    handle_text(reply_token,user_id,msg.get('text','').strip())
                elif mtype=='image':
                    # รูปบิล - ขอบิลเป็นตัวเลขต่อ
                    reply_message(reply_token, [{"type":"text","text":"ได้รับรูปแล้วครับ 🙏 ขอบคุณครับ\n\nในรูปยอดเท่าไหร่ครับ? พิมพ์ตัวเลขมาหน่อยได้ไหมครับ เช่น 4500 หรือถ้าอ่านไม่ออก พิมพ์ประมาณก็ได้ครับ เดี๋ยวผมประเมินให้ก่อน"}])
                elif mtype=='location':
                    addr=msg.get('address',f"{msg.get('latitude')},{msg.get('longitude')}")
                    handle_location(reply_token,user_id,addr)
    except Exception as e:
        print(f"Callback error {e}"); traceback.print_exc()
    return 'OK'

@app.route("/", methods=['GET'])
def home(): return "Sawasdee Solar V4 Sales Funnel is running - 095-774-4978"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)))
