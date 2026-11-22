"""Compose a standalone course paper from the installed skill's verified archive."""
from fractions import Fraction
from pathlib import Path
import re
from urllib.parse import quote
from integration.report_latex import esc

TEMPLATE = Path(__file__).with_name("paper_template.tex")
SECTION_ORDER = ("problem","bounds","four_cell","research","agent_extension","experiments","discussion","sources")
# Fix the revision of the archived inputs so the source line links stay stable.
BASE = "https://github.com/orgyuanbao/MoonshineThermalLab/blob/ece5bbfffbbd722c43c94d691a0b714ffda7b0e5/MoonshineThermalLab/"
NATIVE_EXTENSION_REVISION = "de5b7fb28e46a1749973d6d0a9c36d77a25c08ef"
METHODS = {"analytic":"原解析标量", "sharp_scalar":"最优统一标量", "block_abs":"分块幅度",
           "block_sign":"单端符号", "two_endpoint":"双端点符号"}
HISTORY = ("求解器校验、修复与产物检查", "复核热求解器并补做审核", "构造 POD 基线与失效分析",
           "请求超时，本轮未执行程序", "执行自适应策略开发检查",
           "运行项目提供的冻结基准驱动", "复核热源与归档结果")

def frac(value):
    f = Fraction(str(value))
    if f.denominator == 1:
        return str(f.numerator)
    return ("-" if f < 0 else "") + r"\tfrac{" + str(abs(f.numerator)) + "}{" + str(f.denominator) + "}"

def sci(value):
    mantissa, exponent = f"{float(value):.2e}".split("e")
    power = "10^{" + str(int(exponent)) + "}"
    return power if float(mantissa) == 1 else mantissa + r"\times " + power

def row(cells):
    return " & ".join(str(c) for c in cells) + r" \\"

def four_patterns(modes):
    """Compare all four signed entries and their exact infinity-norm errors."""
    labels = {"constant": "同号", "stripes": "横条纹", "checkerboard": "棋盘格"}
    parts = [
        r"\begin{tikzpicture}[x=1cm,y=1cm,inner sep=0pt]",
        r"\path[use as bounding box] (0,-.10) rectangle (14.85,2.28);",
    ]
    cell = .93
    for index, record in enumerate(modes):
        x = .16 + index * 5.00
        # The recorded vector starts with the bottom row, from left to right.
        for k, sign in enumerate(record["residual"]):
            left = x + cell * (k % 2)
            bottom = .12 + cell * (k // 2)
            fill, foreground = ("white", "black") if sign > 0 else ("black!72", "white")
            symbol = "+" if sign > 0 else "-"
            parts.extend([
                fr"\fill[{fill}] ({left:.3f},{bottom:.3f}) rectangle ++({cell},{cell});",
                fr"\node[text={foreground},font=\Large] at ({left+cell/2:.3f},{bottom+cell/2:.3f}) "
                + r"{$\boldsymbol{" + symbol + r"}$};",
            ])
        parts.extend([
            fr"\draw[black,line width=.55pt] ({x:.3f},.12) rectangle ++({2*cell:.3f},{2*cell:.3f});",
            fr"\draw[black!48,line width=.45pt] ({x+cell:.3f},.12) -- ++(0,{2*cell:.3f});",
            fr"\draw[black!48,line width=.45pt] ({x:.3f},{cell+.12:.3f}) -- ++({2*cell:.3f},0);",
        ])
        text_x = x + 2.12
        value = Fraction(record["error_inf"])
        printed = f"{float(value):.3f}".rstrip("0").rstrip(".")
        relation = "=" if Fraction(printed) == value else r"\approx"
        parts.extend([
            fr"\node[anchor=west,text=ink,font=\small\sffamily\bfseries] at ({text_x:.3f},1.70) "
            + "{" + labels[record["name"]] + "};",
            fr"\node[anchor=west,text=ink,font=\Large] at ({text_x:.3f},1.03) "
            + "{$" + frac(value) + "$};",
            fr"\node[anchor=west,text=muted,font=\small] at ({text_x:.3f},.37) "
            + "{$" + relation + " " + printed + "$};",
        ])
    return "\n".join(parts + [r"\end{tikzpicture}"])


def threshold_chart(case, tolerance):
    """Locate the two verified bounds on a shared, explicitly labelled local axis."""
    from math import ceil, floor, log10

    series = [("仅用位置", case["block_abs"] / tolerance),
              ("位置与正负", case["block_sign"] / tolerance)]
    values = [1.0] + [value for _, value in series]
    rough_step = max(max(values) - min(values), .01) / 3
    unit = 10 ** floor(log10(rough_step))
    step = next(tick * unit for tick in (1, 2, 5, 10) if tick * unit >= rough_step)
    first = min(-1, floor((min(values) - 1) / step))
    last = max(1, ceil((max(values) - 1) / step))
    left, right = 2.46, 10.17
    def coordinate(value):
        return left + ((value-1)/step - first) / (last-first) * (right-left)

    threshold_x = coordinate(1)
    out = [
        r"\begin{tikzpicture}[x=1cm,y=1cm,inner sep=0pt]",
        r"\path[use as bounding box] (0,-.67) rectangle (14.85,2.25);",
        r"\node[anchor=west,text=muted,font=\footnotesize\sffamily] at (0,2.02) {残差信息};",
        fr"\node[anchor=west,text=muted,font=\footnotesize\sffamily] at ({left},2.02) "
        + r"{上界 / 允许误差};",
        r"\node[anchor=west,text=muted,font=\footnotesize\sffamily] at (11.0,2.02) {相对上界};",
        r"\node[anchor=west,text=muted,font=\footnotesize\sffamily] at (13.17,2.02) {判定};",
        fr"\draw[hair,line width=.45pt] ({left},-.10) -- ({right},-.10);",
    ]
    precision = max(2, -floor(log10(step)))
    for offset in range(first, last+1):
        tick = 1 + offset * step
        x = coordinate(tick)
        style = r"black,line width=.80pt,dash pattern=on 4pt off 2pt on 1pt off 2pt" if offset == 0 else r"black!28,line width=.35pt"
        top = 1.70
        out.append(fr"\draw[{style}] ({x:.3f},-.16) -- ({x:.3f},{top});")
        out.append(fr"\node[anchor=north,text=ink,font=\footnotesize] at ({x:.3f},-.23) "
                   + "{$" + f"{tick:.{precision}f}" + "$};")
    out.append(fr"\node[anchor=south,text=muted,font=\scriptsize\sffamily] at ({threshold_x:.3f},1.73) {{阈值}};")
    for index, (label, ratio) in enumerate(series):
        y = 1.33 - index * .83
        x = coordinate(ratio)
        exceeds = ratio > 1
        decision = "报警" if exceeds else "接受"
        line_style = "dash pattern=on 3pt off 1.6pt" if index == 0 else "solid"
        out.extend([
            fr"\node[anchor=west,text=ink,font=\small] at (0,{y:.3f}) {{{label}}};",
            fr"\draw[black,{line_style},line width=1.35pt] ({threshold_x:.3f},{y:.3f}) -- ({x:.3f},{y:.3f});",
            fr"\node[draw=black,fill={'black' if exceeds else 'white'},line width=1.1pt,"
            + ("rectangle" if exceeds else "circle") + fr",minimum size=6pt] at ({x:.3f},{y:.3f}) {{}};",
            fr"\node[anchor=west,text=ink,font=\normalsize] at (11.0,{y:.3f}) " + "{$" + f"{ratio:.3f}$" + "};",
            fr"\node[anchor=west,text=black,font=\small\sffamily\bfseries] at (13.17,{y:.3f}) {{{decision}}};",
        ])
    return "\n".join(out + [r"\end{tikzpicture}"])


def material_links(evidence):
    hashes = evidence["source_sha256"]
    def link(path, label, line=None):
        if path not in hashes:
            raise ValueError("Citation missing from verified evidence: " + path)
        base = (f"https://github.com/orgyuanbao/MoonshineThermalLab/blob/{NATIVE_EXTENSION_REVISION}/MoonshineThermalLab/"
                if path in evidence["agent_extension"]["citation_paths"] else BASE)
        address = base + quote(path,safe="/") + (fr"\#L{line}" if line else "")
        return r"\href{" + address + "}{" + esc(label) + "}"
    turns = evidence["signed"]["turns"]
    four = evidence["four_cell"]
    groups = [
        ("A", "早期求解器与冻结实验", [("evidence/iterations.json","七轮执行与审核"),("evidence/independent-checks.json","独立复核"),(evidence["history"]["oracle_path"],"标量屏障推导")]),
        ("B", "两轮残差界研究", [(turns[0]["proof_path"],"单端证明"),(turns[1]["proof_path"],"双端证明"),("residual_study/moonshine/run_receipts.json","审核回执"),(turns[1]["stdout_path"],"精确反例")]),
        ("C", "四格模态研究", [(four["proof_path"],"模态推导"),("report_example/mode_results.json","逐格分数解"),("report_example/run_evidence.json","执行与审核")]),
        ("D", "独立大网格与补充复核", [("residual_study/results/paired_cases.csv","配对预测"),("residual_study/results/closed_loop_cases.csv","独立部署"),("residual_study/results/summary.json","汇总与计时"),("residual_study/results/fresh_stream.json","追加参数流"),("residual_study/results/exact_audit.json","四格穷举")])]
    groups.append(("E", "自研智能体与反例检验",
                   [(evidence["agent_extension"]["controller_path"], "控制程序"),
                    (evidence["agent_extension"]["tool_path"], "反例工具"),
                    (evidence["agent_extension"]["trace_path"], "调用记录"),
                    (evidence["agent_extension"]["replay_path"], "复放程序"),
                    (evidence["agent_extension"]["http_path"], "接口自测")]))
    out = [
        r"\par\smallskip\begingroup\small\renewcommand{\arraystretch}{1.25}",
        r"\noindent\begin{tabularx}{\linewidth}{@{}l@{\hspace{.9em}}p{.30\linewidth}@{\hspace{.6em}}X@{}}",
        r"\toprule\multicolumn{2}{@{}l}{\sffamily\bfseries 研究材料} & \sffamily\bfseries 原始记录 \\ \midrule",
    ]
    for code, title, files in groups:
        links = r"\hspace{.32em}\textcolor{muted}{/}\hspace{.32em}".join(link(p,l) for p,l in files)
        out.append(row([r"{\sffamily\bfseries " + code + "}", esc(title), links]))
    out.extend([
        r"\bottomrule\end{tabularx}\par\endgroup",
        r"\para{三份原生推导的原式} 下表保留草稿记号，行号链接到原文。",
        r"\par\smallskip\begingroup\small",
        r"\noindent\begin{tabularx}{\linewidth}{@{}p{.30\linewidth}@{\hspace{.75em}}X@{}}",
    ])
    passages = [
        (turns[0],r"^ *(-[a-z]+ +<= +[a-z]+ +<= +[a-z]+)\.? *$","单端包络"),
        (turns[1],r"(?m)^ *(L=[^,\s]+, *U=[^.\s]+)\.? *$","双端包络"),
        (four,r"\$(Au=[^$]+)\$、\$(As=[^$]+)\$、\$(Aq=[^$]+)\$","四格算子作用")]
    for item, pattern, label in passages:
        original = "\n".join(item["proof_text"].splitlines())
        match = re.search(pattern, original, re.MULTILINE)
        if not match:
            raise ValueError("Cited passage missing from " + item["proof_path"])
        n = original.count("\n", 0, match.start(1)) + 1
        excerpt = " / ".join(s.strip() for s in match.groups())
        ref = link(item["proof_path"], label + f"（第 {n} 行）", n)
        out.append(row([ref, r"{\small\ttfamily " + esc(excerpt) + "}"]))
    out.append(r"\end{tabularx}\par\endgroup")
    return "\n".join(out)


def extension_values(trace):
    steps = trace["steps"]
    names = {"weak_signed": r"\norm{G_w r}", "block_position": r"\eta_{\rm pos}",
             "block_signed": r"\eta_{\pm}", "block_two_endpoint": r"\eta_2"}
    rows = []
    for i, step in enumerate(steps, 1):
        result = step["result"]
        formula = names[result["candidate"]]
        if Fraction(result["scale"]) != 1:
            formula = frac(result["scale"]) + r"\," + formula
        outcome = "找到反例" if result["status"] == "counterexample" else "域内未见反例"
        rows.append(row([i, "$" + formula + "$", result["checked_cases"], result["total_cases"], outcome]))
    witness = steps[0]["result"]["witness"]
    scaled = steps[-1]["result"]
    scaled_witness = scaled["witness"]
    def vector(values):
        return r"\bigl(" + ",".join(frac(v) for v in values) + r"\bigr)"
    return {"TOOL_STEPS": "\n".join(rows), "TOOL_H": vector(witness["boundaries"]),
            "TOOL_R": vector(witness["residual"]), "TOOL_BOUND": frac(witness["candidate_bound"]),
            "TOOL_ERROR": frac(witness["true_error_inf"]), "TOOL_MARGIN": frac(witness["violation_margin"]),
            "TOOL_MODEL_CALLS": trace["model_calls"], "HTTP_REQUESTS": trace["http_requests"],
            "SCALE_FACTOR": frac(scaled["scale"]),
            "SCALE_R": vector(scaled_witness["residual"]), "SCALE_ERROR": frac(scaled_witness["true_error_inf"]),
            "SCALE_BOUND": frac(scaled_witness["candidate_bound"])}


def paper_values(d):
    b,summary = d["benchmark"],d["summary"]
    g,pair,closed,total = b["grids"],b["paired"],b["closed"],b["totals"]
    case,fresh,exact = b["case"],d["fresh"],d["exact"]
    four = d["four_cell"]["modes"]
    modes = {s["name"]:s for s in four}
    first,second = d["signed"]["turns"]
    counter = second["stdout"]["counterexample"]
    history, policies = d["history"], fresh["policies"]
    if len(history["turns"]) != len(HISTORY):
        raise ValueError("Seven early stage descriptions must align with the archive.")
    decisions = []
    for m in b["methods"]:
        pa = [pair[str(n)]["old_pre"][m]["alarms"] for n in g]
        cl = [closed[str(n)][m]["fallbacks"] for n in g]
        decisions.append(row([METHODS[m],*pa,*cl]))
    costs = []
    grid_heads = ["$" + str(n) + "^2$" for n in g]
    for n,header in zip(g,grid_heads):
        times = [f"{closed[str(n)][m]['timing_median_s']['policy_total_s']:.4f}" for m in ("analytic","block_sign","two_endpoint")]
        mem = 2 * summary["grids"][str(n)]["one_endpoint_template_bytes"] / 2**20
        costs.append(row([header,*times,f"{mem:.3f}"]))
    stages = []
    for i,(title,t) in enumerate(zip(HISTORY,history["turns"]),1):
        progs = f"{t['successful_python_executions']} / {len(t['python_tool_results'])}"
        passed = f"{t['passed_verifications']} / {t['verification_attempt_count']}"
        stages.append(row([i,title,progs,passed,t["archived_records_reported"]]))
    op,np = (total["old_pre_alarms"][m] for m in ("analytic","two_endpoint"))
    oc,nc = (total["fallbacks"][m] for m in ("analytic","two_endpoint"))
    if first["model"] != second["model"]:
        raise ValueError("The two signed studies cite different models.")
    return {
        **extension_values(d["agent_extension"]),
        "STRIPE":frac(modes["stripes"]["error_inf"]),"CHECKER":frac(modes["checkerboard"]["error_inf"]),
        "STRIPE_RATIO":frac(Fraction(modes["stripes"]["error_inf"])/Fraction(modes["checkerboard"]["error_inf"])),
        "OLDPAIRED":op,"NEWPAIRED":np,"OLDCLOSED":oc,"NEWCLOSED":nc,"PAIRED_SAVED":op-np,"CLOSED_SAVED":oc-nc,
        "EQUIV":"逐例相同" if b["sign_endpoint_max_abs_gap"] == 0 else "存在数值差异",
        "MODE_PICTURE":four_patterns(four),"COUNTER_R":r"\bigl("+",".join(frac(v) for v in counter["r"])+r"\bigr)^\top",
        "UNSAFE":frac(counter["unsafe_bound"]["exact"]),"ACTUAL":frac(counter["actual_error"]["exact"]),
        "NUM_PARAMS":exact["boundary_parameter_cases"],"PATTERNS":exact["ternary_residual_patterns"],"EXACT_PAIRS":exact["case_pattern_pairs"],
        "HISTORY_ROWS":"\n".join(stages),"HIST_SUCCESS":history["totals"]["python_successes"],"HIST_REVIEW":history["totals"]["passed_reviews"],
        "HIST_ARCHIVE":history["totals"]["archived_records"],"FIRST_TOTAL":first["stdout"]["total_tested_pairs"],"FIRST_GAIN":first["stdout"]["strict_gain_pairs"],
        "REVIEW_SMALL":first["reviews"][0]["review_context_characters"],"REVIEW_LARGE":first["reviews"][-1]["review_context_characters"],
        "SECOND_TOTAL":second["stdout"]["tested_parameter_residual_partition_cases"],"SECOND_GAIN":second["stdout"]["strict_interval_improvement_cases"],
        "MODEL":esc(first["model"]),"GRID_STRING":r",\ ".join(f"{n}^2" for n in g),"QUERIES":b["counts"]["queries_per_grid"],
        "PARTITION":r"\times".join(map(str,summary["fixed_partition"])),"TOL":sci(b["tolerance"]),
        "PAIRED_ROWS":b["counts"]["paired_rows"],"CLOSED_ROWS":b["counts"]["closed_rows"],"GRID_HEADS":" & ".join(grid_heads),
        "DECISION_ROWS":"\n".join(decisions),"CASE_N":case["n"],"CASE_I":case["index"]+1,
        "CASE_MU":", ".join(f"{case[k]:.4f}" for k in ("left","right","bottom","top")),"CASE_TRUE":sci(case["error_linf"]),
        "CASE_POS":f"{case['block_abs']:.8f}","CASE_SIGN":f"{case['block_sign']:.8f}",
        "CASE_CHART":threshold_chart(case,b["tolerance"]),"FIXED_EX":"、".join(str(pair[str(n)]["fixed8"]["analytic"]["true_exceedances"]) for n in g),
        "FIXED_RATIOS":"、".join(f"{b['fixed8_median_endpoint_to_analytic'][str(n)]:.3f}" for n in g),
        "COST_ROWS":"\n".join(costs),"REPEATS":b["repeats"],"FRESH_N":fresh["grid"],"FRESH_NQ":fresh["query_count"],
        "SEED":fresh["seed"],"OVERLAP":fresh["shared_with_training_tuning_or_original_stream"],
        "FRESH_OLD":policies["analytic"]["fallbacks"],"FRESH_NEW":policies["two_endpoint"]["fallbacks"],
        "FRESH_PRE":policies["two_endpoint"]["pre_exceedances"]-policies["two_endpoint"]["missed"],"FRESH_RETURN":policies["two_endpoint"]["returned_exceedances"],
        "RETURN_EX":sum(total["returned_exceedances"].values()),"SOURCE_LIST":material_links(d),
    }

def build_paper_tex(evidence: dict, sections: list[str]) -> str:
    """Apply the installed skill's complete, ordered course paper layout."""
    if len(sections) != len(SECTION_ORDER) or set(sections) != set(SECTION_ORDER):
        raise ValueError("The course paper requires each registered section exactly once.")
    parts = re.split(r"^%%PART ([a-z_]+)\n",TEMPLATE.read_text(encoding="utf-8"),flags=re.MULTILINE)
    body = dict(zip(parts[1::2],parts[2::2]))
    if set(body) != set(SECTION_ORDER):
        raise ValueError("Template and registered course paper sections differ.")
    section_break = "\n\\papersectionbreak\n"
    tex = parts[0] + section_break.join(body[k] for k in sections) + "\n\\end{document}\n"
    values = paper_values(evidence)
    return re.sub(r"@@([A-Z_]+)@@", lambda m:str(values[m[1]]), tex)

