import math
from datetime import datetime, date
from zoneinfo import ZoneInfo
from io import BytesIO
from uuid import uuid4

try:
    import qrcode
    from PIL import Image
except ImportError:
    qrcode = None
import streamlit as st

st.set_page_config(page_title="장바구니 메모", page_icon="🛒", layout="centered", initial_sidebar_state="collapsed")

CATEGORIES = ["🥬 야채", "🍎 과일", "🥩 정육·달걀", "🐟 수산", "🥛 유제품", "🍚 쌀·면", "🥫 가공식품", "🧴 생활용품", "📦 기타"]
PRIORITIES = {1: "1 · 꼭 필요", 2: "2 · 가격이 괜찮으면", 3: "3 · 저렴할 때만"}
PAGE_SIZE = 3

st.markdown("""
<style>
.block-container {max-width:540px;padding:0.65rem 0.8rem 1rem;}
header[data-testid="stHeader"] {height:0;background:transparent;}
#MainMenu, footer {visibility:hidden;}
[data-testid="stToolbar"] {display:none;}
[data-testid="stVerticalBlock"] {gap:0.38rem;}
[data-testid="stMetric"] {background:#eef7f1;border-radius:12px;padding:8px 10px;}
[data-testid="stMetricLabel"] p {font-size:0.78rem;}
[data-testid="stMetricValue"] {font-size:1.35rem;}
[data-testid="stPopover"] button {min-height:2.3rem;}
.stButton button {min-height:2.3rem;}
div[data-testid="stHorizontalBlock"] {gap:0.45rem;}
@media(max-width:640px) {
 div[data-testid="stHorizontalBlock"] {flex-wrap:nowrap!important;}
 div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {min-width:0!important;flex:1 1 0!important;}
 .block-container {padding-top:0.5rem;}
}

.stApp {background:#f4f8f6;color:#183e32;}
.block-container {max-width:600px;padding-top:1rem;}
h3 {letter-spacing:-0.045em;font-weight:800!important;color:#174d3b;}
[data-testid="stMetric"] {background:#ffffff;border:1px solid #dcebe3;border-top:3px solid #24815e;border-radius:14px;padding:12px;box-shadow:0 3px 12px #183e3208;}
[data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;color:#176747;font-weight:750;}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:14px!important;}
[data-testid="stExpander"] {background:#ffffff;border-radius:14px;}
.stButton button,[data-testid="stPopover"] button {border-radius:10px;border-color:#cddfd4;font-weight:600;}
.stButton button:hover,[data-testid="stPopover"] button:hover {border-color:#24815e;color:#176747;background:#eaf5ef;}
[data-testid="stNumberInput"] input,[data-testid="stTextInput"] input {font-variant-numeric:tabular-nums;}
[data-testid="stRadio"]>div {background:#e6f0ea;border-radius:12px;padding:8px;gap:12px;}
[data-testid="stCaptionContainer"] {color:#546d60;}
@media(prefers-color-scheme:dark) {
 .stApp {background:#11251d;color:#e3eee7;}
 h3 {color:#9fe0ba;}
 [data-testid="stMetric"],[data-testid="stExpander"] {background:#19362a;border-color:#345743;}
 [data-testid="stMetricValue"] {color:#a6e5bd;}
 [data-testid="stRadio"]>div {background:#19362a;}
 [data-testid="stCaptionContainer"] {color:#b0cab9;}
}
</style>
""", unsafe_allow_html=True)

for key, default in {"items": [], "cart": [], "pantry": [], "page": 0, "notice": "", "view": "살 것"}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def money(value):
    return f"{int(value):,}원"


def notify(message):
    st.session_state.notice = message
    st.rerun()


def new_id():
    return uuid4().hex


head, menu = st.columns([5, 1])
with head:
    st.markdown("### 🛒 오늘의 장바구니")
with menu:
    with st.popover("⚙️", help="QR · 백업 · 도움말"):
        st.caption("앱 주소로 QR 만들기")
        url = st.text_input("배포된 앱의 https 주소", placeholder="https://your-app.streamlit.app")
        if url.strip().startswith("https://") and qrcode is None:
            st.info("QR 생성 패키지가 아직 설치되지 않았어요. 장보기 기능은 정상적으로 사용할 수 있습니다. requirements.txt에 qrcode[pil]을 추가하고 앱을 재시작하면 QR도 만들 수 있어요.")
        elif url.strip().startswith("https://"):
            image = qrcode.make(url.strip())
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            st.image(buffer.getvalue(), width=190)
            st.download_button("QR 이미지 저장", buffer.getvalue(), "shopping-qr.png", "image/png")
        elif url:
            st.warning("https://로 시작하는 실제 배포 주소를 입력하세요.")
        st.caption("QR은 앱을 여는 용도입니다. 다른 휴대폰과 목록이 자동 공유되지는 않습니다.")
        st.divider()
        st.markdown("**백업 / 복원**")
        import json
        backup = json.dumps({"version": 1, "items": st.session_state["items"], "cart": st.session_state.cart, "pantry": st.session_state.pantry}, ensure_ascii=False, indent=2)
        st.download_button("💾 목록·카트 백업", backup, "shopping-backup.json", "application/json")
        uploaded = st.file_uploader("백업 파일 선택", type=["json"])
        if st.button("백업으로 복원", disabled=uploaded is None):
            try:
                data = json.loads(uploaded.getvalue().decode("utf-8"))
                if not isinstance(data, dict) or data.get("version") != 1:
                    raise ValueError("지원하지 않는 백업 형식입니다.")
                restored = {}
                ids = set()
                for collection in ("items", "cart"):
                    rows = data.get(collection)
                    if not isinstance(rows, list) or len(rows) > 1000:
                        raise ValueError("목록은 각각 1,000개까지 복원할 수 있습니다.")
                    restored[collection] = []
                    for row in rows:
                        if not isinstance(row, dict):
                            raise ValueError("잘못된 항목입니다.")
                        name = row.get("name")
                        category = row.get("category")
                        priority = row.get("priority")
                        if not isinstance(name, str) or not name.strip() or len(name) > 40 or category not in CATEGORIES or type(priority) is not int or priority not in PRIORITIES:
                            raise ValueError("상품명·카테고리·중요도를 확인하세요.")
                        clean = {"id": new_id(), "name": name.strip(), "category": category, "priority": priority}
                        if collection == "cart":
                            price, quantity = row.get("price"), row.get("quantity")
                            if type(price) is not int or not 0 <= price <= 100000000 or type(quantity) is not int or not 1 <= quantity <= 10000:
                                raise ValueError("가격 또는 수량이 올바르지 않습니다.")
                            clean.update(price=price, quantity=quantity)
                        restored[collection].append(clean)
                pantry_rows = data.get("pantry", [])
                if not isinstance(pantry_rows, list) or len(pantry_rows) > 1000:
                    raise ValueError("보관함 백업 형식이 올바르지 않습니다.")
                clean_pantry = []
                for row in pantry_rows:
                    if not isinstance(row, dict):
                        raise ValueError("잘못된 보관함 항목입니다.")
                    name, quantity = row.get("name"), row.get("quantity")
                    if not isinstance(name, str) or not name.strip() or len(name) > 40 or type(quantity) is not int or not 1 <= quantity <= 10000:
                        raise ValueError("보관함 상품명 또는 수량이 올바르지 않습니다.")
                    if row.get("location") not in ["냉장", "냉동", "실온"] or row.get("date_type") not in ["소비기한", "유통기한"]:
                        raise ValueError("보관 위치 또는 기한 종류를 확인하세요.")
                    expiry = date.fromisoformat(row["expiry"]).isoformat() if row.get("expiry") else None
                    clean_pantry.append({"id": new_id(), "name": name.strip(), "quantity": quantity, "location": row["location"], "date_type": row["date_type"], "expiry": expiry})
                st.session_state.pantry = clean_pantry
                st.session_state["items"] = restored["items"]
                st.session_state.cart = restored["cart"]
                st.session_state.page = 0
                notify("백업을 복원했어요.")
            except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
                st.error(f"복원 실패: {exc}")
        st.divider()
        st.caption("1 꼭 필요 · 2 가격이 괜찮으면 · 3 저렴할 때만")
        st.caption("수량은 개/봉/팩 등 가격표의 판매 단위 기준 정수입니다. 2개 묶음 5,000원이라면 단가 5,000원, 수량 1로 입력하세요.")
        st.warning("데이터는 현재 접속 세션에만 보관됩니다. 새로고침·연결 종료·서버 재시작 시 사라질 수 있으니 백업하세요. 브라우저 알림이나 가격 조회 기능은 없습니다.")
        confirm = st.checkbox("메모·카트 초기화에 동의합니다 (보관함 유지)")
        if st.button("메모·카트 초기화", disabled=not confirm):
            st.session_state["items"] = []
            st.session_state.cart = []
            st.session_state.page = 0
            notify("새 장보기를 시작해요.")

cart_total = sum(x["price"] * x["quantity"] for x in st.session_state.cart)
a, b = st.columns(2)
a.metric("카트 합계", money(cart_total))
b.metric("남은 메모 / 담은 수량", f"{len(st.session_state['items'])}건 / {sum(x['quantity'] for x in st.session_state.cart)}개")

# Budget stays in this session and does not alter the cart calculation.
budget = st.number_input(
    "💰 지금 가진 돈 / 장보기 예산(원)",
    min_value=0, max_value=1000000000, value=0, step=1000,
    key="shopping_budget", help="0원도 입력할 수 있어요. 현재 카트 합계를 뺀 금액을 보여줍니다.",
)
remaining = int(budget) - cart_total
if remaining >= 0:
    st.caption(f"💰 가진 돈 {money(budget)} · 구매 후 남는 돈 {money(remaining)}")
else:
    st.warning(f"예산보다 {money(-remaining)} 초과했어요. 중요도 2·3 상품을 다시 확인해 보세요.")

if st.session_state.notice:
    st.toast(st.session_state.notice)
    st.session_state.notice = ""

with st.popover("＋ 살 것 추가", use_container_width=True):
    with st.form("add", clear_on_submit=True):
        category = st.selectbox("카테고리", CATEGORIES)
        name = st.text_input("상품명", max_chars=40, placeholder="예: 방울토마토 500g")
        priority = st.selectbox("중요도", [1, 2, 3], format_func=lambda p: PRIORITIES[p])
        submitted = st.form_submit_button("메모 추가", use_container_width=True)
        if submitted:
            if not name.strip():
                st.warning("상품명을 입력하세요.")
            elif len(st.session_state['items']) >= 1000:
                st.warning("메모는 최대 1,000개까지 등록할 수 있습니다.")
            else:
                st.session_state["items"].append({"id": new_id(), "category": category, "name": name.strip(), "priority": priority})
                st.session_state.page = 0
                notify("메모에 추가했어요.")

with st.expander("🧾 가격 정리 · 상품별 금액 / 지출 내역", expanded=False):
    st.caption("현재 카트 기준 · 단가는 판매 단위(개·봉·팩) 기준입니다.")
    if not st.session_state.cart:
        st.info("카트에 상품을 담으면 가격 내역이 여기에 표시됩니다.")
    else:
        sort_order = st.selectbox("정렬", ["금액 높은 순", "금액 낮은 순", "상품명 순"], key="price_sort")
        price_rows = list(st.session_state.cart)
        if sort_order == "상품명 순":
            price_rows.sort(key=lambda row: row["name"])
        else:
            price_rows.sort(key=lambda row: row["price"] * row["quantity"], reverse=sort_order == "금액 높은 순")
        st.dataframe([
            {"상품명": row["name"], "분류": row["category"], "단가(원)": row["price"], "수량": row["quantity"], "합계(원)": row["price"] * row["quantity"]}
            for row in price_rows
        ], hide_index=True, use_container_width=True, height=180)
        st.markdown("**카테고리별 지출**")
        category_totals = {}
        for row in price_rows:
            category_totals[row["category"]] = category_totals.get(row["category"], 0) + row["price"] * row["quantity"]
        st.dataframe([{"분류": category, "지출(원)": amount} for category, amount in sorted(category_totals.items(), key=lambda pair: -pair[1])], hide_index=True, use_container_width=True, height=130)
        st.caption(f"총 {len(price_rows)}종 · {sum(row['quantity'] for row in price_rows)}개 · 합계 {money(cart_total)}")
        import csv
        from io import StringIO
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["상품명", "카테고리", "단가(원)", "수량", "합계(원)"])
        for row in price_rows:
            # Neutralize spreadsheet formula prefixes in user-entered names.
            safe_name = row["name"]
            if safe_name.lstrip().startswith(("=", "+", "-", "@")):
                safe_name = "'" + safe_name
            writer.writerow([safe_name, row["category"], row["price"], row["quantity"], row["price"] * row["quantity"]])
        st.download_button("가격 내역 CSV 내려받기", csv_buffer.getvalue().encode("utf-8-sig"), "shopping_prices.csv", "text/csv")
        with st.popover("✏️ 가격·수량 빠른 수정", use_container_width=True):
            chosen_id = st.selectbox("수정할 상품", [row["id"] for row in price_rows], format_func=lambda rid: next(row["name"] for row in price_rows if row["id"] == rid), key="price_edit_id")
            chosen = next(row for row in st.session_state.cart if row["id"] == chosen_id)
            with st.form(f"price_summary_edit_{chosen_id}"):
                updated_price = st.number_input("단가(원)", min_value=0, max_value=100000000, value=int(chosen["price"]), step=100)
                updated_qty = st.number_input("수량", min_value=1, max_value=10000, value=int(chosen["quantity"]))
                if st.form_submit_button("저장 · 합계 반영", use_container_width=True):
                    chosen.update(price=int(updated_price), quantity=int(updated_qty))
                    notify("가격을 수정했어요. 합계와 남은 예산도 반영했어요.")
        st.caption("보관함 수량은 실제 사용량을 별도로 관리하므로 여기서 수정해도 바뀌지 않습니다.")

view = st.radio("목록 선택", ["살 것", "카트", "보관함"], horizontal=True, label_visibility="collapsed")
if st.session_state.view != view:
    st.session_state.view = view
    st.session_state.page = 0

if view == "살 것":
    f1, f2 = st.columns(2)
    with f1:
        category_filter = st.selectbox("카테고리 필터", ["전체 카테고리"] + CATEGORIES, label_visibility="collapsed")
    with f2:
        priority_filter = st.selectbox("중요도 필터", [0, 1, 2, 3], format_func=lambda p: "모든 중요도" if p == 0 else PRIORITIES[p], label_visibility="collapsed")
    filter_key = (category_filter, priority_filter)
    if st.session_state.get("last_filter") != filter_key:
        st.session_state.last_filter = filter_key
        st.session_state.page = 0
    rows = sorted([x for x in st.session_state["items"] if (category_filter == "전체 카테고리" or x["category"] == category_filter) and (priority_filter == 0 or x["priority"] == priority_filter)], key=lambda x: x["priority"])
elif view == "카트":
    rows = list(reversed(st.session_state.cart))
else:
    st.caption("기한 가까운 순 · 날짜는 포장지에서 직접 확인하세요.")
    with st.popover("＋ 보관 물건 직접 등록", use_container_width=True):
        with st.form("pantry_add", clear_on_submit=True):
            pname = st.text_input("상품명", max_chars=40)
            pqty = st.number_input("보관 수량", 1, 10000, 1)
            ploc = st.selectbox("보관 위치", ["냉장", "냉동", "실온"])
            ptype = st.selectbox("기한 종류", ["소비기한", "유통기한"])
            pdate = st.date_input("포장지에 적힌 기한 (모르면 비워 두세요)", value=None)
            if st.form_submit_button("보관함 등록"):
                if pname.strip():
                    st.session_state.pantry.append({"id": new_id(), "name": pname.strip(), "quantity": int(pqty), "location": ploc, "date_type": ptype, "expiry": pdate.isoformat() if pdate else None})
                    notify("보관함에 등록했어요.")
                else:
                    st.warning("상품명을 입력하세요.")
    rows = sorted(st.session_state.pantry, key=lambda x: x.get("expiry") or "9999-12-31")

pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
st.session_state.page = min(st.session_state.page, pages - 1)
start = st.session_state.page * PAGE_SIZE

if not rows:
    st.info("살 것을 추가해 보세요." if view == "살 것" else ("아직 담은 물건이 없어요." if view == "카트" else "구매한 물건을 보관함에 등록해 보세요."))

for item in rows[start:start + PAGE_SIZE]:
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            # st.text avoids interpreting user-provided names as Markdown/HTML.
            st.text(item["name"])
            if view == "살 것":
                st.caption(f"{item['category']} · {PRIORITIES[item['priority']]}")
            elif view == "카트":
                st.caption(f"{money(item['price'])} × {item['quantity']} = {money(item['price'] * item['quantity'])}")
            else:
                st.caption(f"{item['location']} · {item['quantity']}개")
                if item.get("expiry"):
                    days = (date.fromisoformat(item["expiry"]) - datetime.now(ZoneInfo("Asia/Seoul")).date()).days
                    status = f"🔴 {abs(days)}일 지남" if days < 0 else ("🟠 오늘까지" if days == 0 else f"{'🟠' if days <= 3 else '🟢'} {days}일 남음")
                    st.caption(f"{item['date_type']} {item['expiry']} · {status}")
                else:
                    st.caption("기한 미등록")
        with right:
            if view == "살 것":
                with st.popover("🛒 담기", use_container_width=True):
                    st.text(item["name"])
                    if item["priority"] == 1:
                        st.caption("꼭 필요한 상품이에요. 가격을 확인하고 담으세요.")
                    else:
                        st.info("비싸면 안 사도 돼요! 닫고 메모에 남겨두세요." if item["priority"] == 2 else "특가가 아니라면 다음 기회에 사도 좋아요.")
                    with st.form(f"buy_{item['id']}"):
                        price = st.number_input("실제 단가(원 / 판매 단위)", min_value=0, max_value=100000000, value=1000, step=100)
                        quantity = st.number_input("수량(개·봉·팩)", min_value=1, max_value=10000, value=1, step=1)
                        st.caption("단가 × 수량으로 계산하며, 담기를 누르면 상단 합계가 갱신됩니다.")
                        if st.form_submit_button("가격·수량 확인 후 담기", use_container_width=True):
                            st.session_state.cart.append({**item, "price": int(price), "quantity": int(quantity)})
                            st.session_state["items"] = [x for x in st.session_state["items"] if x["id"] != item["id"]]
                            notify(f"카트에 담았어요 · {money(price * quantity)}")
                    with st.expander("수정 / 메모 삭제"):
                        with st.form(f"edit_{item['id']}"):
                            edited_name = st.text_input("상품명 수정", value=item["name"], max_chars=40)
                            edited_category = st.selectbox("카테고리 수정", CATEGORIES, index=CATEGORIES.index(item["category"]))
                            edited_priority = st.selectbox("중요도 수정", [1, 2, 3], index=item["priority"] - 1, format_func=lambda p: PRIORITIES[p])
                            if st.form_submit_button("수정 저장"):
                                if edited_name.strip():
                                    item.update(name=edited_name.strip(), category=edited_category, priority=edited_priority)
                                    notify("메모를 수정했어요.")
                                else:
                                    st.warning("상품명을 입력하세요.")
                        if st.button("구매하지 않고 메모만 삭제", key=f"delete_{item['id']}"):
                            st.session_state["items"] = [x for x in st.session_state["items"] if x["id"] != item["id"]]
                            notify("메모만 삭제했어요. 카트 금액에는 반영하지 않았어요.")
            elif view == "카트":
                with st.popover("수정·취소", use_container_width=True):
                    st.text(item["name"])
                    if not item.get("stored"):
                        with st.form(f"store_{item['id']}"):
                            st.caption("구매 후 보관함 등록 · 카트 합계는 유지됩니다.")
                            location = st.selectbox("보관 위치", ["냉장", "냉동", "실온"])
                            date_type = st.selectbox("기한 종류", ["소비기한", "유통기한"])
                            expiry = st.date_input("포장지에 적힌 기한 (선택)", value=None)
                            if st.form_submit_button("🏠 구매 완료 · 보관함 등록"):
                                st.session_state.pantry.append({"id": new_id(), "name": item["name"], "quantity": item["quantity"], "location": location, "date_type": date_type, "expiry": expiry.isoformat() if expiry else None})
                                item["stored"] = True
                                notify("보관함에 등록했어요. 카트 합계는 유지됩니다.")
                    else:
                        st.caption("보관함 등록 완료 · 보관 수량과 기한은 보관함에서 별도로 관리하세요.")
                    with st.form(f"cart_edit_{item['id']}"):
                        price = st.number_input("단가(원)", 0, 100000000, int(item["price"]), step=100)
                        quantity = st.number_input("수량", 1, 10000, int(item["quantity"]), step=1)
                        if st.form_submit_button("금액 수정"):
                            item.update(price=int(price), quantity=int(quantity))
                            notify("카트 금액을 수정했어요.")
                    if st.button("↩ 카트에서 빼고 메모로", key=f"undo_{item['id']}"):
                        st.session_state.cart = [x for x in st.session_state.cart if x["id"] != item["id"]]
                        st.session_state["items"].append({k: item[k] for k in ("id", "name", "category", "priority")})
                        notify("카트 금액을 빼고 메모로 돌렸어요.")

            else:
                with st.popover("정리·기한", use_container_width=True):
                    st.text(item["name"])
                    with st.form(f"pantry_edit_{item['id']}"):
                        qty = st.number_input("남은 수량", 1, 10000, int(item["quantity"]))
                        location = st.selectbox("보관 위치", ["냉장", "냉동", "실온"], index=["냉장", "냉동", "실온"].index(item["location"]))
                        date_type = st.selectbox("기한 종류", ["소비기한", "유통기한"], index=["소비기한", "유통기한"].index(item["date_type"]))
                        expiry = st.date_input("포장지에 적힌 기한", value=date.fromisoformat(item["expiry"]) if item.get("expiry") else None)
                        if st.form_submit_button("저장"):
                            item.update(quantity=int(qty), location=location, date_type=date_type, expiry=expiry.isoformat() if expiry else None)
                            notify("보관 정보를 수정했어요.")
                    if st.button("1개 사용", key=f"use_{item['id']}"):
                        if item["quantity"] > 1:
                            item["quantity"] -= 1
                        else:
                            st.session_state.pantry = [x for x in st.session_state.pantry if x["id"] != item["id"]]
                        notify("사용한 수량을 반영했어요.")
                    confirm_delete = st.checkbox("전부 사용·폐기 확인", key=f"confirm_pantry_{item['id']}")
                    if st.button("보관함에서 삭제", disabled=not confirm_delete, key=f"remove_pantry_{item['id']}"):
                        st.session_state.pantry = [x for x in st.session_state.pantry if x["id"] != item["id"]]
                        notify("보관함에서 삭제했어요.")
                    st.caption("날짜 표시는 참고용이며 섭취 가능 여부를 보장하지 않습니다. 개봉 여부·보관 상태와 포장지 안내를 확인하세요. 앱 밖 알림은 전송하지 않습니다.")

prev, label, nxt = st.columns([1, 2, 1])
with prev:
    if st.button("◀", disabled=st.session_state.page == 0, use_container_width=True):
        st.session_state.page -= 1
        st.rerun()
with label:
    st.caption(f"{st.session_state.page + 1} / {pages} 페이지 · {len(rows)}건")
with nxt:
    if st.button("▶", disabled=st.session_state.page >= pages - 1, use_container_width=True):
        st.session_state.page += 1
        st.rerun()
