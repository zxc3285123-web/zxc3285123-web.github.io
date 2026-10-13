# -*- coding: utf-8 -*-
"""
수하물 신호등 — 품목별 페이지 (item/<주소>.html)

_build.py 가 불러서 씁니다. 따로 실행할 필요는 없어요.

글은 _items.py · _dest.py 데이터에서 자동으로 만들어집니다.
새 사실을 지어내지 않도록, 품목 설명(d)·국내선(dom)·검역(io)·나라별 규정(_dest)과
사이트에 이미 실린 분류별 원칙만 조합합니다.

검색 노출(index) 기준
  품목 데이터가 충분한 페이지만 검색엔진에 내보내고, 나머지는 noindex 로 둡니다.
  (내용이 얇은 페이지가 수백 장 색인되면 사이트 전체 평가가 떨어질 수 있어요)
  - 검역·세관 정보(io)가 있거나
  - 도착 국가별 규정(_dest.GROUPS)이 있거나
  - 국내선 예외(dom)·계산기(calc)가 있거나
  - 설명(d)이 MIN_DESC 글자 이상이거나
  - _more.py 에 추가 설명 문단을 써 넣은 품목
  나중에 _more.py 에 설명을 채우면 다음 빌드부터 자동으로 색인 대상이 됩니다.
"""
import re, json, html as _html

MIN_DESC = 60

OXWORD = {"○": "가능", "△": "조건부", "✕": "불가"}
OXCLS = {"○": "o", "△": "t", "✕": "x"}
OXVAR = {"○": "both", "△": "cond", "✕": "ban"}
VLABEL = {"both": "기내 · 위탁 모두 가능", "cabin": "기내만 가능", "checked": "위탁만 가능",
          "cond": "조건부 가능", "ban": "기내 · 위탁 모두 금지"}

# 판정별 설명 — 사이트 원칙(홈의 '헷갈릴 때는 이 다섯 가지')을 풀어 쓴 것
VTEXT = {
 "both": "기내와 위탁 어느 쪽에 넣어도 규정상 문제가 없는 물건입니다. 다만 깨지기 쉽거나 비싼 물건은 "
         "위탁 중 파손·분실되면 보상받기 어려워 기내에 두는 편이 낫고, 반대로 무겁고 부피가 큰 물건은 "
         "기내 무게 한도(국내 항공사 10kg, 외항 저비용항공사는 7kg인 경우가 많음)를 넘기지 않게 위탁으로 보내는 것이 좋습니다.",
 "cabin": "기내에만 가져갈 수 있고 <strong>위탁 수하물에는 넣으면 안 되는</strong> 물건입니다. 대부분 리튬 배터리처럼 "
          "화물칸에서 문제가 생기면 승무원이 대응할 수 없는 경우예요. 카운터에서 짐을 부친 뒤 X-ray에서 발견되면 "
          "호출을 받아 짐을 다시 열어야 하니, 짐을 쌀 때 미리 기내 가방으로 옮겨 두세요.",
 "checked": "기내에는 가져갈 수 없고 <strong>위탁 수하물로 부쳐야 하는</strong> 물건입니다. 날이 있거나 뾰족하거나, "
            "길고 단단해 둔기로 쓰일 수 있는 물건이 여기에 들어갑니다. 보안검색에서 발견되면 그 자리에서 포기(폐기)하거나 "
            "카운터로 돌아가 다시 부쳐야 하니 출발 전에 캐리어에 넣어 두세요.",
 "cond": "<strong>조건을 지키면 가져갈 수 있는</strong> 물건입니다. 용량·개수·포장 상태·노선(국내선/국제선)에 따라 "
         "결과가 달라지므로 위의 조건을 꼭 확인하세요. 조건을 넘기면 보안검색에서 반입이 거절될 수 있습니다.",
 "ban": "<strong>기내에도, 위탁 수하물에도 넣을 수 없는</strong> 물건입니다. 불이 붙거나 터지거나 다른 물건을 녹일 수 있는 "
        "위험물이 대부분이에요. 공항에서 발견되면 폐기해야 하니 처음부터 가져가지 않는 것이 가장 확실합니다.",
}

# 분류별 기본 원칙과 관련 가이드 (가이드 키는 _build.py 의 ORDER 와 같음)
CAT = {
 "전자·배터리": ("전자기기는 <strong>본체보다 배터리</strong>가 기준입니다. 리튬 배터리가 기기에 붙어 있으면 대체로 기내·위탁 모두 "
                "가능하지만, 배터리만 따로 있으면(보조배터리, 여분 배터리) 위탁이 금지되고 기내로만 가져갈 수 있어요. "
                "용량이 큰 배터리는 Wh(와트시)로 판단하며, 100Wh 이하는 대부분 자유롭고 100~160Wh는 항공사 승인이 필요하며 "
                "160Wh를 넘으면 기내·위탁 모두 불가입니다. 위탁할 기기는 전원을 완전히 꺼 두세요.",
                ["battery", "electronics"]),
 "액체·화장품": ("국제선은 <strong>용기당 100ml 이하</strong> 제품만, 1L 이하 투명 지퍼백 하나에 모아 기내로 가져갈 수 있습니다. "
                "기준은 남은 양이 아니라 용기에 표시된 용량이에요. 젤·크림·스프레이·페이스트도 모두 액체로 봅니다. "
                "100ml를 넘는 제품은 위탁 수하물로 보내면 되고, 국내선에는 이 100ml 규정이 적용되지 않습니다.",
                ["liquid", "domestic"]),
 "식품": ("식품은 <strong>두 번 걸러집니다</strong>. 공항 보안검색에서는 국물·소스·장류처럼 흐르는 음식이 액체 규정(국제선 100ml)에 걸리고, "
         "도착한 나라 세관·검역에서는 육류·유제품·과일 같은 원재료가 문제가 됩니다. 보안검색을 통과했다고 해서 "
         "도착 국가에서 반입이 허용되는 것은 아니니, 해외로 가져갈 때는 아래 나라별 기준을 함께 보세요.",
         ["quarantine", "customs", "liquid"]),
 "날붙이·공구": ("날이 있거나 뾰족한 물건은 <strong>기본적으로 위탁</strong>입니다. 날 길이 6cm 이하 가위와 손톱깎이 정도만 "
                "기내에 들어가요. 드라이버·렌치 같은 공구도 길이에 따라 기내가 막힐 수 있습니다. "
                "위탁할 때는 날을 감싸 수하물 직원이 다치지 않게 포장해 주세요.",
                ["banned", "checked"]),
 "스포츠·레저": ("배트·골프채·등산스틱처럼 <strong>길고 단단한 장비</strong>는 날이 없어도 둔기로 분류돼 기내 반입이 막힙니다. "
                "부피가 큰 장비는 항공사마다 특수 수하물 규격과 요금이 따로 있으니 예약한 항공사의 기준을 미리 확인하고, "
                "필요하면 사전 신청을 해 두는 편이 공항에서 시간을 아낍니다.",
                ["sports", "banned"]),
 "의약·의료": ("여행 중 필요한 약은 <strong>기내 가방에</strong> 두는 것이 원칙입니다. 액체 약·시럽·주사용 약품은 "
              "필요한 만큼이라면 100ml를 넘어도 반입이 허용되는 예외가 있지만, 보안검색에서 따로 신고하고 "
              "처방전이나 영문 진단서를 보여 줄 수 있으면 훨씬 수월합니다. 나라에 따라 반입이 제한되는 성분도 있어요.",
              ["medicine", "liquid"]),
 "위험물": ("불이 붙거나, 터지거나, 다른 물건을 녹이는 물건은 <strong>기내도 위탁도 금지</strong>되는 경우가 대부분입니다. "
           "라이터처럼 몸에 지니는 1개만 예외로 허용되는 품목도 있지만, 그런 물건은 반대로 위탁 수하물에 넣을 수 없어요. "
           "위험물 규정은 국내선과 국제선이 같습니다.",
           ["banned", "checked"]),
 "유아·반려": ("아기와 반려동물은 <strong>항공사마다 규정이 크게 다른</strong> 영역입니다. 유모차·카시트는 무료로 부칠 수 있는 경우가 많고, "
              "분유·이유식·아기 음료는 액체 규정의 예외로 필요한 만큼 기내에 가져갈 수 있어요. "
              "반려동물은 기내 동반 가능 여부와 무게 기준을 예약 단계에서 항공사에 꼭 확인하세요.",
              ["baby", "pet"]),
 "의류·생활": ("옷과 생활용품은 대부분 <strong>제한이 없지만</strong>, 무게와 부피가 문제입니다. 기내 가방 무게 한도를 넘기지 않게 "
              "무거운 것은 위탁으로 보내고, 액체·스프레이가 섞인 생활용품만 따로 챙겨 보세요.",
              ["packing", "season"]),
 "기타·귀중품": ("현금·여권·귀금속처럼 <strong>잃어버리면 곤란한 물건</strong>은 반드시 기내에 두세요. 위탁 수하물은 "
                "분실·파손 시 항공사 배상 한도가 정해져 있어 고가품은 제대로 보상받기 어렵습니다. "
                "일정 금액이 넘는 현금이나 물품은 출입국 때 세관 신고 대상이 될 수 있어요.",
                ["customs", "checked"]),
}

IOL = {"ok": ("반입 가능", "both"), "declare": ("신고 필요", "checked"), "ban": ("반입 금지", "ban")}
DL = {"ok": ("반입 가능", "both"), "declare": ("신고 · 조건부", "checked"),
      "ban": ("반입 금지", "ban"), "warn": ("확인 필요", "cond")}


def plain(s):
    return re.sub(r"<[^>]+>", "", s)


def short(n):
    """'태블릿 · 아이패드' → '태블릿·아이패드', 괄호는 그대로"""
    return n.replace(" · ", "·")


def josa(word, a, b):
    """받침 있으면 a, 없으면 b (예: 은/는, 이/가)"""
    w = re.sub(r"[^가-힣A-Za-z0-9]", "", word)
    if not w:
        return b
    ch = w[-1]
    if "가" <= ch <= "힣":
        return a if (ord(ch) - 0xAC00) % 28 else b
    return a if ch.lower() in "lmn0136789" else b


def build(*, ITEMS, CATS, SLUGS, DGROUPS, DCOUNTRIES, DRULES, GORDER, GNAMES,
          POSTS_BY_KEY, page, AD, SITE_NAME, SITE_URL, MORE=None):
    MORE = MORE or {}
    """품목 페이지를 모두 만들고 (페이지 경로 목록, 색인 대상 경로 목록, 품목→경로) 를 돌려준다"""
    slug_of, missing = {}, []
    for i, it in enumerate(ITEMS):
        s = SLUGS.get(it["n"])
        if not s:
            s = f"item-{i + 1}"
            missing.append(it["n"])
        slug_of[it["n"]] = s
    if missing:
        print("  ⚠ _slugs.py 에 주소가 없는 품목:", ", ".join(missing))

    def url(it):
        return f"item/{slug_of[it['n']]}.html"

    def rich(it):
        return bool(it.get("io") or it["n"] in DGROUPS or it.get("dom") or it.get("calc")
                    or it["n"] in MORE or len(plain(it["d"])) >= MIN_DESC)

    written, indexable = [], []
    for it in ITEMS:
        nm = short(it["n"])
        ox = it["ox"]
        v = it["v"]
        idx = rich(it)

        # ── 신호등 두 칸
        def sig(label, mk):
            var = OXVAR[mk]
            return (f'<div class="sig" style="--c:var(--v-{var});--cbg:var(--v-{var}-bg);--cl:var(--v-{var}-line)">'
                    f'<span class="sig-l">{label}</span><b class="sig-m">{mk}</b>'
                    f'<span class="sig-w">{OXWORD[mk]}</span></div>')
        signal = f'<div class="sigs">{sig("기내", ox[0])}{sig("위탁", ox[1])}</div>'

        # ── 국내선 예외
        dom_html = ""
        if it.get("dom"):
            dm = it["dom"]
            dom_html = (f'<div class="callout ok"><span class="label">국내선은 다릅니다</span>'
                        f'<p>국내선 기준 — 기내 <span class="mk {OXCLS[dm["ox"][0]]}">{dm["ox"][0]}</span> · '
                        f'위탁 <span class="mk {OXCLS[dm["ox"][1]]}">{dm["ox"][1]}</span> '
                        f'({VLABEL[dm["v"]]}). {dm["d"]}</p></div>')

        calc_html = ""
        if it.get("calc") == "wh":
            calc_html = ('<p>내 제품이 몇 Wh인지 모르겠다면 판별기의 <strong>용량 계산기</strong>에 mAh와 전압을 넣어 보세요. '
                         f'<a href="../tool.html?q={_html.escape(it["n"])}">계산기 열기 →</a></p>')
        elif it.get("calc") == "ml":
            calc_html = ('<p>용기 용량이 헷갈리면 판별기의 <strong>용기 계산기</strong>로 기내 반입 여부를 바로 확인할 수 있어요. '
                         f'<a href="../tool.html?q={_html.escape(it["n"])}">계산기 열기 →</a></p>')

        more_html = (f'<h2>{_html.escape(nm)}, 이것만 알면 됩니다</h2><p>{MORE[it["n"]]}</p>'
                     if it["n"] in MORE else "")

        # ── 검역·세관
        io_html = ""
        if it.get("io"):
            io = it["io"]
            rows = []
            if io.get("out"):
                rows.append(f'<tr><td>🛫 한국에서 나갈 때</td><td>목적지 확인</td><td>{io["out"]}</td></tr>')
            if io.get("inv") or io.get("ind"):
                lab, var = IOL.get(io.get("inv", ""), ("—", "cond"))
                rows.append(f'<tr><td>🛬 한국으로 들어올 때</td>'
                            f'<td style="font-weight:700;color:var(--v-{var})">{lab}</td><td>{io.get("ind", "—")}</td></tr>')
            io_html = (f'<h2>해외 여행이라면 — 검역 · 세관</h2>'
                       f'<p>보안검색을 통과해도 <strong>도착한 나라 세관이나 검역에서</strong> 막힐 수 있는 품목입니다.</p>'
                       f'<div class="tablewrap"><table><thead><tr><th style="min-width:130px">구분</th>'
                       f'<th style="width:96px">판정</th><th>기준</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

        # ── 도착 국가별
        dest_html, dest_faq = "", None
        g = DGROUPS.get(it["n"])
        if g:
            rows, bans, oks = [], [], []
            for c in DCOUNTRIES:
                t = DRULES[c["id"]]
                if g not in t:
                    continue
                vv, txt = t[g]
                lab, var = DL[vv]
                cname = c["name"].split(" ")[0]
                if vv == "ban":
                    bans.append(cname)
                if vv == "ok":
                    oks.append(cname)
                rows.append(f'<tr><td>{c["flag"]} {c["name"]}</td>'
                            f'<td style="font-weight:700;color:var(--v-{var})">{lab}</td>'
                            f'<td style="font-size:13px">{txt}</td></tr>')
            dest_html = (f'<h2>나라별로 가져가도 될까 — {len(rows)}개국</h2>'
                         f'<p>{_html.escape(GNAMES[g])} 기준입니다. 같은 물건이라도 <strong>도착하는 나라</strong>에 따라 결과가 달라져요. '
                         f'<strong>확인 필요</strong>는 공식 자료에서 여행자 기준을 찾지 못한 칸입니다.</p>'
                         f'<div class="tablewrap"><table><thead><tr><th style="min-width:150px">도착 국가</th>'
                         f'<th style="width:104px">판정</th><th>기준과 주의할 점</th></tr></thead>'
                         f'<tbody>{"".join(rows)}</tbody></table></div>'
                         f'<p style="font-size:13px;color:var(--muted)">조사 기준일 2026년 9월. 각국 세관·검역 당국 공식 안내 기준이며, '
                         f'규정이 자주 바뀌니 출발 전 한 번 더 확인하세요. <a href="../country.html">14개국 전체 규정 보기 →</a></p>')
            parts = []
            if bans:
                parts.append(f'{", ".join(bans)}{josa(bans[-1], "은", "는")} 반입 금지')
            if oks:
                parts.append(f'{", ".join(oks)}{josa(oks[-1], "은", "는")} 반입 가능')
            if parts:
                dest_faq = (f"{nm}{josa(nm, '을', '를')} 해외에 가져가도 되나요?",
                            "도착 국가에 따라 다릅니다. 조사한 나라 중 " + ", ".join(parts) +
                            "으로 확인됐고, 나머지는 신고 조건이 붙거나 확인이 필요합니다. 위 표에서 나라별 기준을 확인하세요.")

        # ── 별칭
        alias = [a for a in it.get("k", "").split() if a]
        alias_html = ""
        if alias:
            chips = " ".join(f'<span class="chip">{_html.escape(a)}</span>' for a in alias[:16])
            alias_html = (f'<h2>이렇게도 불러요</h2><p>판별기에서 아래 이름으로 검색해도 '
                          f'<strong>{_html.escape(nm)}</strong> 결과가 나옵니다.</p><p class="chips">{chips}</p>')

        # ── FAQ
        d_plain = plain(it["d"])
        ans = {"○": "네, 가능합니다.", "△": "조건에 따라 가능합니다.", "✕": "아니요, 안 됩니다."}
        faq = [
            (f"{nm} 기내에 들고 탈 수 있나요?", f"{ans[ox[0]]} {d_plain}"),
            (f"{nm} 위탁 수하물로 부쳐도 되나요?", {
                "both": "네, 가능합니다. 다만 위탁 중 파손·분실되면 보상받기 어려우니 비싸거나 깨지기 쉬운 물건은 기내에 두는 편이 낫습니다.",
                "cabin": "아니요, 위탁 수하물에는 넣을 수 없습니다. 짐을 부치기 전에 기내 가방으로 옮겨 두세요.",
                "checked": "네, 위탁 수하물로 부쳐야 합니다. 기내에는 가져갈 수 없으니 보안검색 전에 캐리어에 넣어 두세요.",
                "cond": f"{ans[ox[1]]} 기내와 위탁의 조건이 다를 수 있으니 위의 설명에 적힌 조건을 확인하세요.",
                "ban": "아니요. 기내와 위탁 모두 금지된 물건이라 공항에서 발견되면 폐기해야 합니다.",
            }[v]),
        ]
        if it.get("dom"):
            faq.append((f"국내선에서도 {nm} 규정이 같나요?", f"다릅니다. {plain(it['dom']['d'])}"))
        if dest_faq:
            faq.append(dest_faq)
        if len(faq) < 3:
            faq.append(("공항에서 판단이 다르면 어떻게 하나요?",
                        "이 페이지는 국토교통부 고시와 항공사 공식 규정을 바탕으로 정리한 참고 정보입니다. "
                        "실제 반입 여부는 보안검색요원과 항공사의 판단이 우선하니, 애매한 물건은 탑승수속 카운터에서 먼저 물어보세요."))
        faq_html = "<h2>자주 묻는 질문</h2>" + "".join(
            f'<h3 style="font-size:16.5px;margin-top:22px">{q}</h3><p>{a}</p>' for q, a in faq)
        ld = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": q,
                              "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
        crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "수하물 판별기", "item": f"{SITE_URL}/tool.html"},
            {"@type": "ListItem", "position": 2, "name": it["c"], "item": f"{SITE_URL}/tool.html#cat-{CATS.index(it['c']) + 1}"},
            {"@type": "ListItem", "position": 3, "name": it["n"], "item": f"{SITE_URL}/{url(it)}"}]}

        # ── 관련 품목: 같은 분류에서 같은 판정 먼저
        same = [x for x in ITEMS if x["c"] == it["c"] and x is not it]
        same.sort(key=lambda x: (x["v"] != v, ITEMS.index(x)))
        rel = "".join(
            f'<a class="rel" href="{slug_of[x["n"]]}.html"><span>{x["e"]}</span>'
            f'<b>{_html.escape(short(x["n"]))}</b>'
            f'<em><span class="mk {OXCLS[x["ox"][0]]}">{x["ox"][0]}</span>'
            f'<span class="mk {OXCLS[x["ox"][1]]}">{x["ox"][1]}</span></em></a>' for x in same[:8])

        cat_text, gkeys = CAT[it["c"]]
        guides = "".join(
            f'<a class="card" href="../{POSTS_BY_KEY[k]["slug"]}"><h3>{POSTS_BY_KEY[k]["title"]}</h3>'
            f'<p>{POSTS_BY_KEY[k]["desc"][:70]}…</p></a>' for k in gkeys if k in POSTS_BY_KEY)

        q = _html.escape(it["n"])
        lede_v = {"both": "기내와 위탁 모두 가능합니다.", "cabin": "기내만 가능하고 위탁은 안 됩니다.",
                  "checked": "위탁으로 부쳐야 하고 기내에는 가져갈 수 없습니다.",
                  "cond": "조건을 지키면 가져갈 수 있습니다.", "ban": "기내도 위탁도 안 됩니다."}[v]

        body = f"""<section class="hero-band">
  <div class="wrap hero-in">
    <p class="eyebrow"><a href="../tool.html#cat-{CATS.index(it['c']) + 1}" style="color:inherit;text-decoration:none">{it['c']}</a></p>
    <h1><span aria-hidden="true">{it['e']}</span> {_html.escape(nm)}, 비행기에 가져갈 수 있나요?</h1>
    <p class="lede">결론부터 — <strong>{lede_v}</strong></p>
  </div>
</section>

<main class="wrap">
  <article class="post">
    {signal}
    <div class="callout" style="border-left-color:var(--v-{v})">
      <span class="label">{VLABEL[v]} · 국제선 기준</span>
      <p>{it['d']}</p>
    </div>
    {dom_html}
    {more_html}
    {calc_html}
    <h2>‘{VLABEL[v]}’{josa(VLABEL[v], '은', '는')} 무슨 뜻인가요</h2>
    <p>{VTEXT[v]}</p>
    {AD}
    <h2>{it['c']} 물건의 기본 원칙</h2>
    <p>{cat_text}</p>
    {io_html}
    {dest_html}
    {alias_html}
    {faq_html}
    <div class="toolcta">
      <p><strong>항공사·노선을 골라 다시 확인하기</strong><br>판별기에서 국내선·국제선, 도착 국가를 바꾸면 결과가 함께 바뀝니다.</p>
      <a class="btn" href="../tool.html?q={q}">판별기에서 {_html.escape(nm)} 보기</a>
    </div>
    {AD}
    <h2>같은 분류의 다른 물건</h2>
    <div class="rels">{rel}</div>
    <p style="margin-top:14px"><a href="index.html">전체 품목 {len(ITEMS)}개 보기 →</a></p>
    <h2>관련 규정 가이드</h2>
    <div class="cards">{guides}</div>
    <p style="font-size:13px;color:var(--muted);margin-top:26px">국토교통부 「항공기 내 반입금지 위해물품」 고시와 국내외 항공사 공식 규정을 바탕으로 정리한 참고 정보입니다.
    실제 반입 여부는 항공사와 공항 보안검색의 판단에 따릅니다.</p>
  </article>
</main>"""

        title = f"{nm} 기내 반입 될까? 위탁 수하물은? | {SITE_NAME}"
        desc = (f"{nm}: 기내 {OXWORD[ox[0]]}, 위탁 {OXWORD[ox[1]]}. {d_plain} "
                + ("도착 국가별 반입 기준까지 정리했습니다." if g else "국내선·국제선 기준을 함께 정리했습니다."))
        desc = _html.escape(desc, quote=True)
        head = (f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'
                f'<script type="application/ld+json">{json.dumps(crumbs, ensure_ascii=False)}</script>\n')
        p = page(path=url(it), title=_html.escape(title), desc=desc, body=body,
                 cur="tool.html", depth=1, head_extra=head, robots=None if idx else "noindex, follow")
        written.append(p)
        if idx:
            indexable.append(p)

    # ── 품목 전체 목록 (item/index.html)
    secs = []
    for c in CATS:
        rows = [x for x in ITEMS if x["c"] == c]
        links = "".join(
            f'<a class="rel" href="{slug_of[x["n"]]}.html"><span>{x["e"]}</span>'
            f'<b>{_html.escape(short(x["n"]))}</b>'
            f'<em><span class="mk {OXCLS[x["ox"][0]]}">{x["ox"][0]}</span>'
            f'<span class="mk {OXCLS[x["ox"][1]]}">{x["ox"][1]}</span></em></a>' for x in rows)
        secs.append(f'<h2 id="c{CATS.index(c) + 1}" style="scroll-margin-top:90px">{c} '
                    f'<span style="color:var(--muted);font-weight:400;font-size:14px">{len(rows)}개</span></h2>'
                    f'<div class="rels">{links}</div>')
    nav = " ".join(f'<a class="btn ghost" href="#c{CATS.index(c) + 1}">{c}</a>' for c in CATS)
    page(path="item/index.html", cur="tool.html", depth=1,
         title=f"품목별 기내 반입 · 위탁 수하물 규정 {len(ITEMS)}개 | {SITE_NAME}",
         desc=f"보조배터리·라이터·향수·김치·가위 등 {len(ITEMS)}개 품목의 기내 반입과 위탁 수하물 가능 여부를 품목별 페이지로 정리했습니다.",
         body=f"""<section class="hero-band"><div class="wrap hero-in">
    <p class="eyebrow">Items A to Z</p>
    <h1>품목별 규정 {len(ITEMS)}개</h1>
    <p class="lede">물건을 누르면 기내·위탁 판정과 이유, 국내선 예외, 나라별 반입 기준까지 한 페이지로 볼 수 있어요.
    기호는 <span class="mk o">○</span> 가능 · <span class="mk t">△</span> 조건부 · <span class="mk x">✕</span> 불가, 앞이 기내 뒤가 위탁입니다.</p>
  </div></section>
<main class="wrap"><article class="post" style="max-width:none">
<p style="display:flex;gap:6px;flex-wrap:wrap">{nav}</p>
{"".join(secs)}
{AD}
</article></main>""")
    written.append("item/index.html")
    indexable.append("item/index.html")
    return written, indexable, {n: f"item/{s}.html" for n, s in slug_of.items()}
