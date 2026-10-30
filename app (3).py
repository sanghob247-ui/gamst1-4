import math
from datetime import datetime
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
</style>
""", unsafe_allow_html=True)

for key, default in {"items": [], "cart": [], "page": 0, "notice": "", "view": "살 것"}.items():
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
    st.markdown("### 🛒 장바구니 메모")
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
        backup = json.dumps({"version": 1, "items": st.session_state["items"], "cart": st.session_state.cart}, ensure_ascii=False, indent=2)
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
        confirm = st.checkbox("전체 초기화에 동의합니다")
        if st.button("전체 초기화", disabled=not confirm):
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

view = st.radio("목록 선택", ["살 것", "카트"], horizontal=True, label_visibility="collapsed")
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
else:
    rows = list(reversed(st.session_state.cart))

pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
st.session_state.page = min(st.session_state.page, pages - 1)
start = st.session_state.page * PAGE_SIZE

if not rows:
    st.info("살 것을 추가해 보세요." if view == "살 것" else "아직 담은 물건이 없어요.")

for item in rows[start:start + PAGE_SIZE]:
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            # st.text avoids interpreting user-provided names as Markdown/HTML.
            st.text(item["name"])
            if view == "살 것":
                st.caption(f"{item['category']} · {PRIORITIES[item['priority']]}")
            else:
                st.caption(f"{money(item['price'])} × {item['quantity']} = {money(item['price'] * item['quantity'])}")
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
            else:
                with st.popover("수정·취소", use_container_width=True):
                    st.text(item["name"])
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
