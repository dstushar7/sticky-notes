#!/usr/bin/env python3
"""
benchmark_resource.py - Automated Resource Impact Profiler for Sticky Notes

Measures and records:
- CPU Usage (%)
- Memory Footprint (RSS in MB)
- Disk Write Activity (Total Bytes Written & Write Syscalls)
over a configurable idle/active time window.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


def get_process_stats(pid: int) -> dict:
    """Read CPU time, RSS, and I/O write bytes for the given PID."""
    stat_path = f"/proc/{pid}/stat"
    io_path = f"/proc/{pid}/io"
    status_path = f"/proc/{pid}/status"

    if not os.path.exists(stat_path):
        raise ProcessLookupError(f"Process PID {pid} is no longer running.")

    # 1. CPU Time (utime + stime)
    with open(stat_path, "r") as f:
        stat_parts = f.read().split()
        utime = int(stat_parts[13])
        stime = int(stat_parts[14])
        total_cpu_ticks = utime + stime

    # 2. Memory RSS
    rss_kb = 0
    with open(status_path, "r") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                rss_kb = int(line.split()[1])
                break

    # 3. Disk I/O (write_bytes, syscw)
    write_bytes = 0
    syscw = 0
    if os.path.exists(io_path):
        try:
            with open(io_path, "r") as f:
                for line in f:
                    if line.startswith("write_bytes:"):
                        write_bytes = int(line.split()[1])
                    elif line.startswith("syscw:"):
                        syscw = int(line.split()[1])
        except PermissionError:
            pass

    return {
        "timestamp": time.time(),
        "cpu_ticks": total_cpu_ticks,
        "rss_mb": round(rss_kb / 1024, 2),
        "write_bytes": write_bytes,
        "syscw": syscw,
    }


def find_stickynotes_pid(prefer_snap: bool = False, prefer_local: bool = False) -> int | None:
    """Find running Sticky Notes PID."""
    pids = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        cmdline_file = proc / "cmdline"
        try:
            cmdline = cmdline_file.read_bytes().replace(b"\x00", b" ").decode(errors="ignore")
            if "run_stickynotes" in cmdline or "stickynotes" in cmdline:
                if "python" in cmdline and "benchmark" not in cmdline:
                    pid = int(proc.name)
                    is_snap = "/snap/" in cmdline
                    pids.append((pid, is_snap, cmdline))
        except (PermissionError, FileNotFoundError):
            continue

    if not pids:
        return None

    if prefer_snap:
        snap_pids = [p[0] for p in pids if p[1]]
        if snap_pids:
            return snap_pids[0]
    if prefer_local:
        local_pids = [p[0] for p in pids if not p[1]]
        if local_pids:
            return local_pids[0]

    return pids[0][0]


def run_benchmark(pid: int, duration: int, label: str) -> dict:
    clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    num_cpus = os.cpu_count() or 1

    print(f"\n=======================================================")
    print(f" Profiling Target: {label}")
    print(f" PID: {pid} | Duration: {duration}s | CPUs: {num_cpus}")
    print(f" (Please leave the app IDLE to measure baseline usage)")
    print(f"=======================================================\n")

    initial_stats = get_process_stats(pid)
    prev_stats = initial_stats
    cpu_samples = []
    rss_samples = [initial_stats["rss_mb"]]

    start_time = time.time()
    for sec in range(1, duration + 1):
        time.sleep(1.0)
        curr_stats = get_process_stats(pid)

        # Calculate instantaneous CPU % over the 1-second interval
        d_ticks = curr_stats["cpu_ticks"] - prev_stats["cpu_ticks"]
        d_time = curr_stats["timestamp"] - prev_stats["timestamp"]
        cpu_pct = (d_ticks / clk_tck / d_time) * 100.0
        cpu_samples.append(cpu_pct)
        rss_samples.append(curr_stats["rss_mb"])

        d_write_kb = (curr_stats["write_bytes"] - prev_stats["write_bytes"]) / 1024
        d_syscw = curr_stats["syscw"] - prev_stats["syscw"]

        bar = "█" * min(20, int(cpu_pct * 4))
        print(
            f"[{sec:02d}/{duration}s] "
            f"CPU: {cpu_pct:5.2f}% {bar:<10} | "
            f"RAM: {curr_stats['rss_mb']:6.1f} MB | "
            f"Disk Write: {d_write_kb:6.1f} KB/s ({d_syscw} writes)"
        )
        prev_stats = curr_stats

    final_stats = prev_stats
    total_time = final_stats["timestamp"] - initial_stats["timestamp"]
    total_write_bytes = final_stats["write_bytes"] - initial_stats["write_bytes"]
    total_syscw = final_stats["syscw"] - initial_stats["syscw"]

    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    avg_rss = sum(rss_samples) / len(rss_samples) if rss_samples else 0.0
    write_rate_kbs = (total_write_bytes / 1024) / total_time if total_time > 0 else 0.0

    summary = {
        "label": label,
        "pid": pid,
        "duration_seconds": round(total_time, 1),
        "avg_cpu_pct": round(avg_cpu, 2),
        "max_cpu_pct": round(max(cpu_samples) if cpu_samples else 0.0, 2),
        "avg_memory_rss_mb": round(avg_rss, 2),
        "total_disk_write_kb": round(total_write_bytes / 1024, 2),
        "disk_write_rate_kbs": round(write_rate_kbs, 2),
        "total_write_syscalls": total_syscw,
    }

    print(f"\n--- Summary for: {label} ---")
    print(f"Average Idle CPU:       {summary['avg_cpu_pct']}% (Max: {summary['max_cpu_pct']}%)")
    print(f"Average RAM (RSS):      {summary['avg_memory_rss_mb']} MB")
    print(f"Total Disk Data Written:{summary['total_disk_write_kb']} KB")
    print(f"Disk Write Rate:        {summary['disk_write_rate_kbs']} KB/s")
    print(f"Write System Calls:     {summary['total_write_syscalls']} calls")
    print("-------------------------------------------------------\n")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Profile Sticky Notes Resource Impact")
    parser.add_argument("--pid", type=int, help="Process ID to profile (auto-detected if omitted)")
    parser.add_argument("--duration", type=int, default=20, help="Benchmark duration in seconds (default: 20)")
    parser.add_argument("--label", type=str, default="Sticky Notes", help="Label for this benchmark run")
    parser.add_argument("--save", type=str, help="Save result as JSON file (e.g. baseline.json)")
    parser.add_argument("--compare", type=str, help="Compare with a saved baseline JSON file")
    parser.add_argument("--snap", action="store_true", help="Auto-detect snap app specifically")
    parser.add_argument("--local", action="store_true", help="Auto-detect local app specifically")
    args = parser.parse_args()

    pid = args.pid
    if not pid:
        pid = find_stickynotes_pid(prefer_snap=args.snap, prefer_local=args.local)
        if not pid:
            print("Error: Could not find any running Sticky Notes process.", file=sys.stderr)
            print("Please provide --pid manually or start the application.", file=sys.stderr)
            sys.exit(1)

    result = run_benchmark(pid, args.duration, args.label)

    if args.save:
        with open(args.save, "w") as f:
            json.dump(result, f, indent=2)
        print(f"✓ Results saved to: {args.save}")

    if args.compare and os.path.exists(args.compare):
        with open(args.compare, "r") as f:
            baseline = json.load(f)

        print("\n========================= BEFORE vs AFTER COMPARISON =========================")
        print(f"{'Metric':<28} | {baseline['label']:<22} | {result['label']:<22} | {'Change':<15}")
        print("-" * 92)

        def row(name, b_val, a_val, unit="", invert=False):
            diff = a_val - b_val
            pct = (diff / b_val * 100) if b_val != 0 else (0.0 if diff == 0 else 100.0)
            sign = "+" if diff > 0 else ""
            status = "improved" if diff < 0 else ("regressed" if diff > 0 else "neutral")
            diff_str = f"{sign}{diff:.2f}{unit} ({sign}{pct:.1f}%)"
            print(f"{name:<28} | {f'{b_val:.2f}{unit}':<22} | {f'{a_val:.2f}{unit}':<22} | {diff_str:<15}")

        row("Avg Idle CPU", baseline["avg_cpu_pct"], result["avg_cpu_pct"], "%")
        row("Avg RAM (RSS)", baseline["avg_memory_rss_mb"], result["avg_memory_rss_mb"], " MB")
        row("Total Disk Written", baseline["total_disk_write_kb"], result["total_disk_write_kb"], " KB")
        row("Write Rate", baseline["disk_write_rate_kbs"], result["disk_write_rate_kbs"], " KB/s")
        row("Write Syscalls", baseline["total_write_syscalls"], result["total_write_syscalls"], "")
        print("==============================================================================\n")


if __name__ == "__main__":
    main()
