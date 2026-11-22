"""Compose a standalone course paper from the installed skill's verified archive."""
from fractions import Fraction
from pathlib import Path
import re
from urllib.parse import quote
from integration.report_latex import esc

TEMPLATE = Path(__file__).with_name("paper_template.tex")
SECTION_ORDER = ("problem","bounds","four_cell","research","experiments","discussion","sources")
# Fix the revision of the archived inputs so the source line links stay stable.
BASE = "https://github.com/orgyuanbao/MoonshineThermalLab/blob/ece5bbfffbbd722c43c94d691a0b714ffda7b0e5/MoonshineThermalLab/"
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
    """Place the saved signed vector in the row ordering of its four-cell solver."""
    parts = [r"\begin{tikzpicture}[x=1cm,y=1cm]"]
    labels = {"constant":"同号","stripes":"横条纹","checkerboard":"棋盘格"}
    for index, record in enumerate(modes):
        origin = index * 4.1
        for k, sign in enumerate(record["residual"]):
            x, y = origin + .78 * (k % 2), .78 * (k // 2)
            color = "umber!22" if sign > 0 else "accent!24"
            symbol = "+" if sign > 0 else "-"
            parts.append(fr"\fill[{color}] ({x:.2f},{y:.2f}) rectangle ++(.75,.75);")
            parts.append(fr"\node at ({x+.375:.3f},{y+.375:.3f}) {{\large " + "$"+symbol+"$};")
        parts.append(fr"\node at ({origin+.76:.2f},-.34) " + "{" + labels[record["name"]] + "};")
        parts.append(fr"\node[text=ink] at ({origin+.76:.2f},-.84) " + r"{$\norm e=" + frac(record["error_inf"]) + "$};")
    parts.append(r"\end{tikzpicture}")
    return "\n".join(parts)

def threshold_chart(case, tolerance):
    vals = [(label,case[key]/tolerance) for label,key in (("只用位置","block_abs"),("再分正负","block_sign"))]
    scale = 9.5 / (1.18 * max([1.0] + [value for _,value in vals]))
    out = [r"\begin{tikzpicture}[x=1cm,y=1cm]",
           fr"\draw[densely dashed,ink] ({scale:.3f},-.19) -- ++(0,1.3);",
           fr"\node[above,text=ink,font=\footnotesize] at ({scale:.3f},1.12) {{阈值 $1$}};"]
    for j,(label,value) in enumerate(vals):
        y = .74 - .64*j
        color = "umber" if value > 1 else "accent"
        out.append(fr"\node[anchor=east,font=\small] at (-.15,{y:.2f}) {{{label}}};")
        out.append(fr"\draw[{color},line width=5pt] (0,{y:.2f}) -- ({value*scale:.3f},{y:.2f});")
        out.append(fr"\node[anchor=west,font=\small] at ({value*scale+.1:.3f},{y:.2f}) {{{value:.3f}}};")
    out.append(r"\end{tikzpicture}")
    return "\n".join(out)

def material_links(evidence):
    hashes = evidence["source_sha256"]
    def link(path, label, line=None):
        if path not in hashes:
            raise ValueError("Citation missing from verified evidence: " + path)
        address = BASE + quote(path,safe="/") + (f"#L{line}" if line else "")
        return r"\href{" + address + "}{" + esc(label) + "}"
    turns = evidence["signed"]["turns"]
    four = evidence["four_cell"]
    groups = [
        ("A　早期求解器和冻结实验", [("evidence/iterations.json","七轮执行与审核回执"),("evidence/independent-checks.json","独立复核"),(evidence["history"]["oracle_path"],"标量屏障推导")]),
        ("B　两轮残差界研究", [(turns[0]["proof_path"],"单端证明"),(turns[1]["proof_path"],"双端证明"),("residual_study/moonshine/run_receipts.json","审核回执"),(turns[1]["stdout_path"],"精确反例")]),
        ("C　四格模态专轮", [(four["proof_path"],"模态推导"),("report_example/mode_results.json","逐格分数解"),("report_example/run_evidence.json","原生执行与审核")]),
        ("D　独立大网格与补充复核", [("residual_study/results/paired_cases.csv","配对预测"),("residual_study/results/closed_loop_cases.csv","独立部署"),("residual_study/results/summary.json","汇总与计时"),("residual_study/results/fresh_stream.json","追加参数流"),("residual_study/results/exact_audit.json","四格独立穷举")])]
    out = []
    for title,files in groups:
        out.append(r"\para{" + title + "}" + "、".join(link(p,l) for p,l in files) + "。")
    out.append(r"\para{三份原生推导的原式} 以下各式保留所在草稿的记号，链接指向对应原文行。")
    passages = [
        (turns[0],r"^ *(-[a-z]+ +<= +[a-z]+ +<= +[a-z]+)\.? *$","单端包络"),
        (turns[1],r"(?m)^ *(L=[^,\s]+, *U=[^.\s]+)\.? *$","双端包络"),
        (four,r"\$(Au=[^$]+)\$、\$(As=[^$]+)\$、\$(Aq=[^$]+)\$","四格算子作用")]
    for item,pattern,label in passages:
        original = "\n".join(item["proof_text"].splitlines())
        match = re.search(pattern,original,re.MULTILINE)
        if not match:
            raise ValueError("Cited passage missing from " + item["proof_path"])
        n = original.count("\n",0,match.start(1)) + 1
        excerpt = " / ".join(s.strip() for s in match.groups())
        out.append(r"\par\noindent\hspace{1.3em}" + link(item["proof_path"],label+f"（第 {n} 行）",n)
                   + r"\quad{\small\ttfamily " + esc(excerpt) + "}")
    return "\n".join(out)

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
    tex = parts[0] + "\n\\clearpage\n".join(body[k] for k in sections) + "\n\\end{document}\n"
    values = paper_values(evidence)
    return re.sub(r"@@([A-Z_]+)@@", lambda m:str(values[m[1]]), tex)

