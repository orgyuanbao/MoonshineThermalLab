"""Interactive, isolated thermal-research entry for the original Moonshine runtime."""
from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import os
from pathlib import Path
import sys
import uuid

import run_moonshine as runner

DATA = Path(__file__).resolve().parent / "thermal"
EXAMPLE_REPORT = Path(__file__).resolve().parent / "report_example" / "report.pdf"
STAGES = {
    "1": ("建模与最小校验", "01_model.txt"),
    "2": ("完整模型与固定 POD 基线", "02_baseline.txt"),
    "3": ("寻找失效案例与误差分析", "03_failure.txt"),
    "4": ("改进方法与独立测试", "04_improve.txt"),
    "5": ("残差的位置、正负与误差上界", "05_signed_residual.txt"),
}


def configure():
    runner.select_project(
        DATA, project="thermal-rom", title="Moonshine 热仿真研究",
        continue_prompt="继续热仿真降阶与误差控制项目。先读取研究记忆和实际产物，补齐最近一轮未完成项；实际运行并复核。",
        entrypoint=__file__,
    )


def check_dependencies():
    versions = {}
    for name in ("numpy", "scipy", "matplotlib"):
        try:
            versions[name] = importlib.import_module(name).__version__
        except ImportError as exc:
            raise RuntimeError(f"缺少 {name}。请使用本项目 .venv 安装科学计算依赖。") from exc
    return versions


def make_request(stage=None, supplement=""):
    text = (DATA / "problem.md").read_text(encoding="utf-8")
    if stage:
        text += "\n\n本轮指定任务：\n" + (DATA / "prompts" / STAGES[stage][1]).read_text(encoding="utf-8")
    else:
        text += "\n\n本轮任务：先读取当前项目记忆与产物，在本题范围内按以下补充要求推进。"
    if supplement.strip():
        text += "\n\n用户补充：\n" + supplement.strip()
    text += (
        "\n\n轮次纪律：先检查前置产物是否真实存在、是否可复现；缺失时先补齐并明确尚未进入本阶段。"
        "保留旧版本和失败记录。只根据本轮实际证据报告进度，不把菜单阶段号当作完成度。"
        "每轮限定一个可执行的小目标，预算不足时保存下一步。"
    )
    path = DATA / "requests" / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_step(stage=None, supplement="", *, max_calls=16):
    check_dependencies()
    prompt = make_request(stage, supplement)
    print("本次只推进一轮；一轮可能仅完成所选阶段的一部分。", flush=True)
    return runner.run_research(prompt, max_calls=max_calls)


def read_multiline():
    print("输入补充要求；另起一行输入 END 并回车才会提交。直接输入 END 取消。")
    lines = []
    while True:
        line = input("要求> " if not lines else "续写（END 提交）> ")
        if line.strip().upper() == "END":
            return "\n".join(lines).strip()
        lines.append(line)


def open_latest_report():
    import json
    selection = runner.DATA_ROOT / "active_session.json"
    if not selection.is_file():
        if EXAMPLE_REPORT.is_file():
            print("当前项目还没有本地研究轮次。打开随仓四格示例；这是已保存的报告。")
            os.startfile(str(EXAMPLE_REPORT))
        else:
            print("当前项目还没有研究轮次。先选择 1 推进一轮研究。")
        return
    evidence = runner.resolve_evidence_reference(json.loads(selection.read_text(encoding="utf-8"))["latest_evidence"])
    if not evidence or not (evidence / "turn_summary.json").is_file():
        print("最近一轮尚无结束记录。研究结束后可在这里查看报告。")
        return
    status = runner.retry_report(evidence.name)
    folder = evidence / "report"
    if status == 0:
        pdf = folder / "report.pdf"
        os.startfile(str(pdf if pdf.is_file() else folder))
    else:
        print("本轮尚无可展示的报告。可选 2 查看状态。")


def build_course_paper(output=None, *, tex_only=False, open_result=False):
    from integration.course_paper import generate_course_paper
    folder, receipt = generate_course_paper(runner.HOME, output=output, tex_only=tex_only)
    print("综合课程论文：", receipt["message"])
    print("保存位置：", folder)
    print("已核对来源：", receipt["source_count"], "份。排版模型调用：", receipt["model_calls"])
    if receipt["status"] == "compile_failed":
        return 2
    if open_result:
        os.startfile(str(folder / "paper.pdf" if receipt["status"] == "compiled" else folder))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=["check", "status", "run", "report", "paper"])
    parser.add_argument("--turn", help="重新生成报告的轮次标识，默认取最近一轮")
    parser.add_argument("--output", type=Path, help="综合论文的输出目录，默认每次创建新目录")
    parser.add_argument("--tex-only", action="store_true", help="生成综合论文的 TeX 和回执，跳过 PDF 编译")
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--max-calls", type=int, default=16)
    args = parser.parse_args()
    if args.action != "paper" and (args.output is not None or args.tex_only):
        parser.error("--output 和 --tex-only 适用于 paper")
    if args.action == "paper" and (args.turn or args.stage):
        parser.error("paper 使用综合论文的全部归档来源，请勿同时指定研究轮次或阶段")
    if not 1 <= args.max_calls <= 24:
        parser.error("--max-calls 必须在 1 到 24 之间")
    if args.action == "run" and not args.stage:
        parser.error("命令行运行时请指定 --stage 1 到 5")
    configure()
    if args.action == "check":
        print("科学计算依赖：", check_dependencies())
        for _, name in STAGES.values():
            if not (DATA / "prompts" / name).is_file():
                raise RuntimeError("缺少轮次任务：" + name)
        original = sys.argv
        try:
            sys.argv = [str(Path(runner.__file__)), "check", "--max-calls", str(args.max_calls)]
            return runner.main()
        finally:
            sys.argv = original
    if args.action == "status":
        runner.show_status()
        return 0
    if args.action == "report":
        return runner.retry_report(args.turn)
    if args.action == "paper":
        return build_course_paper(args.output, tex_only=args.tex_only)
    if args.action == "run":
        return run_step(args.stage, max_calls=args.max_calls)

    print("Moonshine 热仿真研究")
    print("选题：离散导热方程中的残差与温度误差。")
    print("阶段 5 研究残差的位置和符号，可从小网格开始；阶段 1 至 4 提供原导热模型与降阶基线。")
    print("打开菜单不会发起研究；选择研究阶段或提交补充要求后才调用模型。")
    while True:
        print("\n当前模型：", runner.model_display())
        print("1  选择阶段并推进一轮\n2  查看研究状态\n3  打开研究产物文件夹\n4  切换模型\n5  补充要求并推进一轮\n6  查看或重新生成最近一轮报告\n7  汇总历轮推导与大网格实验，生成课程论文\n0  退出")
        answer = input("输入数字并回车：").strip()
        if answer == "0":
            return 0
        try:
            if answer == "1":
                for key, (label, _) in STAGES.items():
                    print(key, " ", label)
                stage = input("选择阶段 1 到 5，直接回车取消：").strip()
                if not stage:
                    continue
                if stage not in STAGES:
                    print("没有这个阶段。")
                    continue
                supplement = input("可补充一句要求，直接回车使用预设任务：").strip()
                run_step(stage, supplement, max_calls=args.max_calls)
            elif answer == "2":
                runner.show_status()
            elif answer == "3":
                path = runner.HOME / "projects" / runner.PROJECT
                path.mkdir(parents=True, exist_ok=True)
                os.startfile(str(path))
            elif answer == "4":
                runner.switch_model()
            elif answer == "5":
                supplement = read_multiline()
                if supplement:
                    run_step(supplement=supplement, max_calls=args.max_calls)
            elif answer == "6":
                open_latest_report()
            elif answer == "7":
                build_course_paper(open_result=True)
            else:
                print("请选择 0 到 7。")
        except Exception as exc:
            print("本轮未完成：", exc, flush=True)
            print("可选 2 查看已保存记录，补充失败信息后重试。")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n已停止；已写出的记录保留。")
        raise SystemExit(130)
    except Exception as exc:
        print("无法启动：", exc, file=sys.stderr, flush=True)
        raise SystemExit(1)
