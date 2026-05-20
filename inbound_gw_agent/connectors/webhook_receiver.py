from __future__ import annotations

import base64 as _base64
import csv as _csv
import hashlib
import hmac
import io as _io
import re as _re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from inbound_gw_agent.config import get_settings
from inbound_gw_agent.models.message import InboundMessage, MessageSource

if TYPE_CHECKING:
    from inbound_gw_agent.pipeline import Pipeline

log = structlog.get_logger()

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>마스턴투자운용 — 오류 자동수정 시스템</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%231a4fff'/><stop offset='1' stop-color='%230ea5e9'/></linearGradient></defs><rect width='32' height='32' rx='7' fill='url(%23g)'/><text x='16' y='22' font-family='system-ui,sans-serif' font-size='16' font-weight='900' fill='white' text-anchor='middle'>M</text></svg>">
<style>
:root {
  --bg:       #080f1c;
  --bg-s:     #0b1527;
  --bg-e:     #0e1d38;
  --bg-card:  #0c1830;
  --bg-hov:   #132040;
  --bd:       rgba(255,255,255,.06);
  --bd2:      rgba(255,255,255,.10);
  --bd-acc:   rgba(50,120,255,.35);
  --tx:       #dde6f4;
  --tx2:      #7fa0c0;
  --tx3:      #435a78;
  --acc:      #2b6dff;
  --acc-dim:  rgba(43,109,255,.13);
  --c-crit:   #ff4444;
  --c-high:   #ff7a29;
  --c-med:    #ffb820;
  --c-low:    #4a90ff;
  --c-info:   #38d9c4;
  --c-ok:     #2eca8a;
  --c-fix:    #a855f7;
  --c-spam:   #435a78;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--tx);font-size:13px;overflow:hidden}
a{color:inherit;text-decoration:none}
button{font-family:inherit;cursor:pointer}

/* ── HEADER ── */
.hdr{height:58px;background:var(--bg-s);border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;padding:0 24px;position:relative;z-index:10;flex-shrink:0}
.hdr-l{display:flex;align-items:center;gap:14px}
.logo{width:43px;height:34px;background:linear-gradient(135deg,#1a4fff,#0ea5e9);border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:9px;color:#fff;letter-spacing:.1em;flex-shrink:0;box-shadow:0 2px 12px rgba(43,109,255,.4)}
.hdr-titles{display:flex;flex-direction:column}
.hdr-co{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.09em;text-transform:uppercase}
.hdr-sys{font-size:13.5px;font-weight:700;letter-spacing:-.02em}
.hdr-sep{width:1px;height:26px;background:var(--bd)}
.live{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:700;color:var(--c-ok);letter-spacing:.05em}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--c-ok);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.hdr-r{display:flex;align-items:center;gap:16px}
.clock{font-size:12px;color:var(--tx2);font-variant-numeric:tabular-nums;font-weight:500;letter-spacing:.02em}
.last-upd{font-size:11px;color:var(--tx3)}

/* ── LAYOUT ── */
.wrap{display:flex;height:calc(100vh - 58px)}

/* ── SIDEBAR ── */
.sb{width:214px;flex-shrink:0;background:var(--bg-s);border-right:1px solid var(--bd);display:flex;flex-direction:column;overflow-y:auto;padding:18px 0 14px}
.sb-sec{padding:0 14px;margin-bottom:22px}
.sb-lbl{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.1em;text-transform:uppercase;padding:0 8px;margin-bottom:6px}
.nav-item{display:flex;align-items:center;gap:9px;padding:7px 9px;border-radius:7px;cursor:pointer;color:var(--tx2);font-size:12.5px;font-weight:500;transition:all .12s;margin-bottom:1px}
.nav-item:hover{background:var(--bg-hov);color:var(--tx)}
.nav-item.active{background:var(--acc-dim);color:var(--acc)}
.nav-ico{width:15px;height:15px;flex-shrink:0;opacity:.85}
.nav-cnt{margin-left:auto;background:var(--c-crit);color:#fff;font-size:10px;font-weight:800;padding:1px 5px;border-radius:999px;min-width:18px;text-align:center;line-height:15px}
.nav-soon{margin-left:auto;font-size:9.5px;color:var(--tx3);background:var(--bg-e);padding:2px 6px;border-radius:4px;font-weight:600}
.sb-cats{padding:0 14px;display:flex;flex-direction:column;gap:2px}
.sb-cat{display:flex;align-items:center;justify-content:space-between;padding:5px 8px;border-radius:6px}
.sb-cat:hover{background:var(--bg-hov)}
.sb-cat-name{font-size:11.5px;color:var(--tx2)}
.sb-cat-n{font-size:11.5px;font-weight:700}
.sb-foot{margin-top:auto;padding:0 14px}
.sb-hint{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:11px 12px;font-size:11px;color:var(--tx3);line-height:1.55}
.sb-hint b{display:block;color:var(--tx2);font-weight:600;margin-bottom:3px;font-size:11.5px}
.sb-hint .cdwn{color:var(--acc);font-weight:700;margin-top:5px}

/* ── MAIN ── */
.main{flex:1;overflow-y:auto;display:flex;flex-direction:column}
.main-in{padding:22px 26px;flex:1;display:flex;flex-direction:column;gap:18px}

/* ── PAGE HDR ── */
.pg-hdr{display:flex;align-items:flex-start;justify-content:space-between}
.pg-title{font-size:17px;font-weight:800;letter-spacing:-.03em}
.pg-sub{font-size:11.5px;color:var(--tx2);margin-top:3px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:7px 13px;border-radius:7px;font-size:12px;font-weight:600;border:none;transition:all .12s}
.btn-ghost{background:transparent;color:var(--tx2);border:1px solid var(--bd2)}
.btn-ghost:hover{background:var(--bg-e);color:var(--tx)}

/* ── STATS ROW ── */
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
.scard{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:14px 16px;position:relative;overflow:hidden}
.scard::before{content:'';position:absolute;top:0;left:0;right:0;height:2.5px;border-radius:10px 10px 0 0}
.scard.s-all::before{background:var(--acc)}
.scard.s-crit::before{background:var(--c-crit)}
.scard.s-task::before{background:var(--c-high)}
.scard.s-jira::before{background:var(--c-med)}
.scard.s-info::before{background:var(--c-ok)}
.sc-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:7px}
.sc-val{font-size:26px;font-weight:900;letter-spacing:-.04em;line-height:1;margin-bottom:3px}
.scard.s-all .sc-val{color:var(--tx)}
.scard.s-crit .sc-val{color:var(--c-crit)}
.scard.s-task .sc-val{color:var(--c-high)}
.scard.s-jira .sc-val{color:var(--c-med)}
.scard.s-info .sc-val{color:var(--c-ok)}
.sc-desc{font-size:10.5px;color:var(--tx3)}

/* ── FILTER ROW ── */
.frow{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.srch-wrap{position:relative;flex:1;min-width:180px;max-width:300px}
.srch-ico{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--tx3);width:13px;height:13px;pointer-events:none}
.srch{width:100%;background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:7px 10px 7px 28px;color:var(--tx);font-size:12px;outline:none;transition:border-color .15s}
.srch::placeholder{color:var(--tx3)}
.srch:focus{border-color:var(--bd-acc)}
.fsel{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:7px 26px 7px 10px;color:var(--tx);font-size:12px;outline:none;cursor:pointer;-webkit-appearance:none;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath fill='%23435a78' d='M5 6 0 0h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 9px center;transition:border-color .15s}
.fsel:focus{border-color:var(--bd-acc)}
.fsel option{background:var(--bg-e);color:var(--tx)}
.ftabs{display:flex;background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:3px;gap:2px}
.ftab{padding:5px 11px;border-radius:5px;cursor:pointer;font-size:11px;font-weight:600;color:var(--tx2);transition:all .12s;letter-spacing:.03em}
.ftab.active{background:var(--bg-card);color:var(--tx);box-shadow:0 1px 4px rgba(0,0,0,.35)}
.ftab:hover:not(.active){color:var(--tx)}

/* ── BANNER ── */
.banner{background:linear-gradient(135deg,rgba(43,109,255,.07),rgba(168,85,247,.07));border:1px dashed rgba(43,109,255,.22);border-radius:10px;padding:12px 16px;display:flex;align-items:center;gap:12px}
.banner-ico{font-size:22px;flex-shrink:0}
.banner-tx{font-size:11px;color:var(--tx2);line-height:1.55}
.banner-tx strong{display:block;font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px}

/* ── TABLE ── */
.tcard{background:var(--bg-card);border:1px solid var(--bd);border-radius:12px;overflow:hidden;flex:1;min-height:0}
.twrap{overflow:auto;max-height:calc(100vh - 400px);min-height:200px}
table{width:100%;border-collapse:collapse;min-width:800px}
thead th{padding:10px 14px;text-align:left;font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--bd);background:rgba(0,0,0,.18);white-space:nowrap;position:sticky;top:0;z-index:2}
th.sortable{cursor:pointer;user-select:none}
th.sortable:hover{color:var(--tx)}
th.sort-asc::after{content:" ▲";font-size:9px;color:var(--acc);vertical-align:middle}
th.sort-desc::after{content:" ▼";font-size:9px;color:var(--acc);vertical-align:middle}
tbody tr{border-bottom:1px solid var(--bd);cursor:pointer;transition:background .08s}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:var(--bg-hov)}
tbody tr.sel{background:var(--acc-dim)}
tbody td{padding:11px 14px;font-size:12px;color:var(--tx2)}
.t-id{font-family:'SF Mono','Fira Code',monospace;font-size:11px;color:var(--tx3)}
.t-sub{color:var(--tx);font-weight:500;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.t-snd{max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.t-time{font-variant-numeric:tabular-nums;white-space:nowrap;font-size:11.5px}
.jlnk{color:#ffc94d;font-size:11px;font-weight:600}
.jlnk:hover{text-decoration:underline}

/* ── SEVERITY ── */
.sv{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
.sv-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.sv-crit{background:rgba(255,68,68,.11);color:#ff7070}.sv-crit .sv-dot{background:var(--c-crit)}
.sv-high{background:rgba(255,122,41,.11);color:#ffaa70}.sv-high .sv-dot{background:var(--c-high)}
.sv-med{background:rgba(255,184,32,.1);color:#ffce60}.sv-med .sv-dot{background:var(--c-med)}
.sv-low{background:rgba(74,144,255,.11);color:#80b6ff}.sv-low .sv-dot{background:var(--c-low)}
.sv-info{background:rgba(56,217,196,.09);color:#38d9c4}.sv-info .sv-dot{background:var(--c-info)}
.sv-spam{background:rgba(67,90,120,.15);color:#6a8299}.sv-spam .sv-dot{background:var(--c-spam)}
.sv-unk{background:rgba(168,85,247,.1);color:#c090ff}.sv-unk .sv-dot{background:var(--c-fix)}

/* ── PERSONAL PRIORITY ── */
.pp{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.04em}
.pp-high{background:rgba(255,68,68,.13);color:#ff7070}
.pp-med{background:rgba(255,184,32,.11);color:#ffce60}
.pp-low{background:rgba(74,144,255,.1);color:#80b6ff}
.pp-none{background:rgba(100,120,150,.1);color:#6a8299}
/* ── EMAIL CATEGORY ── */
.ec{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600}
.ec-urg{background:rgba(255,68,68,.13);color:#ff7070}
.ec-mine{background:rgba(43,109,255,.13);color:#6b9fff}
.ec-ref{background:rgba(56,217,196,.1);color:#38d9c4}
.ec-ign{background:rgba(67,90,120,.14);color:#6a8299}
.ec-none{background:rgba(100,120,150,.1);color:#6a8299}
/* ── ACTION REQUIRED ── */
.ar-y{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(255,68,68,.12);color:#ff8080}
.ar-n{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600;background:rgba(56,217,196,.08);color:#38d9c4}
.btn-jira{padding:7px 14px;background:var(--acc);color:#fff;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .15s}
.btn-jira:hover{opacity:.85}
.btn-jira:disabled{opacity:.45;cursor:default}

/* ── STATUS ── */
.st{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:600;white-space:nowrap}
.st-new{background:rgba(139,163,194,.1);color:#8ba3c2}
.st-jira{background:rgba(255,201,77,.1);color:#ffc94d}
.st-urg{background:rgba(255,68,68,.11);color:#ff7070}
.st-pulse{width:6px;height:6px;border-radius:50%;background:currentColor;animation:blink 1.4s infinite;flex-shrink:0}

/* ── SOURCE ── */
.src{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600}
.src-ol{background:rgba(0,114,198,.15);color:#5aacff}
.src-tm{background:rgba(97,66,196,.15);color:#a07aff}

/* ── EMPTY ── */
.empty{padding:56px 20px;text-align:center;color:var(--tx3);font-size:12px}

/* ── DETAIL OVERLAY ── */
.ov{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:200;opacity:0;pointer-events:none;transition:opacity .2s}
.ov.open{opacity:1;pointer-events:all}

/* ── DETAIL PANEL ── */
.dp{position:fixed;right:0;top:0;bottom:0;width:440px;background:var(--bg-s);border-left:1px solid var(--bd2);z-index:201;transform:translateX(100%);transition:transform .22s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden}
.dp.open{transform:translateX(0)}
.dp-hdr{padding:18px 22px;border-bottom:1px solid var(--bd);display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-shrink:0}
.dp-hdr-l{min-width:0}
.dp-id{font-size:10.5px;color:var(--tx3);margin-bottom:4px;font-family:'SF Mono','Fira Code',monospace}
.dp-title{font-size:14px;font-weight:700;line-height:1.35;color:var(--tx)}
.dp-close{width:28px;height:28px;border:none;background:var(--bg-e);color:var(--tx2);border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:15px;line-height:1;transition:all .12s}
.dp-close:hover{background:var(--bg-hov);color:var(--tx)}
.dp-body{flex:1;overflow-y:auto;padding:18px 22px;display:flex;flex-direction:column;gap:18px}
.dp-sec-lbl{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.1em;text-transform:uppercase;margin-bottom:8px}
.dp-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.dp-field{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:9px 11px}
.dp-field-lbl{font-size:10px;color:var(--tx3);margin-bottom:3px;font-weight:600;letter-spacing:.04em}
.dp-field-val{font-size:12px;color:var(--tx);font-weight:500;word-break:break-all;min-height:16px}

/* ── AUTOFIX CARD ── */
.af-card{background:linear-gradient(135deg,rgba(168,85,247,.07),rgba(43,109,255,.07));border:1px solid rgba(168,85,247,.22);border-radius:10px;padding:14px}
.af-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.af-title{font-size:12px;font-weight:700;color:#b07fff;display:flex;align-items:center;gap:5px}
.af-badge{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:700}
.af-badge.done{background:rgba(46,202,138,.12);color:#4cd9a0}
.af-badge.pend{background:rgba(168,85,247,.15);color:#c090ff}
.af-badge.urg{background:rgba(255,68,68,.12);color:#ff7070}
.af-steps{display:flex;flex-direction:column;gap:7px}
.af-step{display:flex;align-items:center;gap:8px;font-size:11.5px}
.step-ic{width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;flex-shrink:0;line-height:1}
.ic-done{background:rgba(46,202,138,.18);color:#4cd9a0}
.ic-pend{background:rgba(67,90,120,.2);color:#435a78}
.lbl-done{color:var(--tx2)}
.lbl-pend{color:var(--tx3)}
.af-prog{background:var(--bg-e);border-radius:4px;height:3px;margin-top:12px;overflow:hidden}
.af-fill{height:100%;background:linear-gradient(90deg,#a855f7,#2b6dff);border-radius:4px;transition:width .5s}

.dp-foot{padding:13px 22px;border-top:1px solid var(--bd);flex-shrink:0}
.dp-foot-tx{font-size:10.5px;color:var(--tx3)}

/* ── BODY TEXT ── */
.dp-body-text{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;font-size:11.5px;color:var(--tx2);line-height:1.65;white-space:pre-wrap;word-break:break-word;max-height:280px;overflow-y:auto}

/* ── EDIT META ── */
.dp-edit-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}
.dp-edit-row{display:flex;flex-direction:column;gap:3px}
.dp-select,.dp-text-input{background:var(--bg-s);border:1px solid var(--bd2);border-radius:6px;color:var(--tx);font-size:11.5px;padding:5px 8px;width:100%}
.dp-select{cursor:pointer}
.dp-select:focus,.dp-text-input:focus{outline:none;border-color:var(--acc)}
.btn-save-meta{padding:7px 18px;background:var(--acc);border:none;border-radius:7px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;transition:opacity .12s}
.btn-save-meta:hover{opacity:.85}
.btn-save-meta:disabled{opacity:.5;cursor:not-allowed}
.dp-save-msg{font-size:11px;margin-left:8px;vertical-align:middle}
/* ── ERROR ANALYSIS ── */
.btn-analyze{padding:7px 16px;background:linear-gradient(135deg,#e53935,#b71c1c);border:none;border-radius:7px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;transition:opacity .12s;display:inline-flex;align-items:center;gap:6px}
.btn-analyze:hover{opacity:.85}
.btn-analyze:disabled{opacity:.5;cursor:not-allowed}
.ea-result{margin-top:12px;display:flex;flex-direction:column;gap:8px}
.ea-card{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:11px 14px}
.ea-card-title{font-size:11px;font-weight:700;color:var(--tx3);letter-spacing:.05em;text-transform:uppercase;margin-bottom:6px}
.ea-card-body{font-size:12px;color:var(--tx);line-height:1.6;white-space:pre-wrap;word-break:break-word}
.ea-cause{display:flex;align-items:flex-start;gap:8px;padding:5px 0;border-bottom:1px solid var(--bd)}
.ea-cause:last-child{border-bottom:none}
.ea-lk{display:inline-block;padding:1px 7px;border-radius:4px;font-size:10px;font-weight:700;flex-shrink:0;margin-top:2px}
.ea-lk-h{background:rgba(255,68,68,.15);color:#ff7070}
.ea-lk-m{background:rgba(255,165,0,.15);color:#ffb347}
.ea-lk-l{background:rgba(120,120,120,.15);color:var(--tx3)}
.btn-delete{padding:7px 16px;background:transparent;border:1px solid rgba(255,68,68,.4);border-radius:7px;color:#ff7070;font-size:12px;font-weight:700;cursor:pointer;transition:all .12s}
.btn-delete:hover{background:rgba(255,68,68,.1);border-color:#ff7070}
.btn-row-del{background:transparent;border:none;color:rgba(255,112,112,.5);font-size:13px;cursor:pointer;padding:2px 5px;border-radius:4px;line-height:1;transition:color .1s,background .1s}
.btn-row-del:hover{color:#ff7070;background:rgba(255,68,68,.12)}

/* ── SETTINGS MODAL ── */
.modal-ov{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:300;display:none}
.modal-ov.open{display:block}
.settings-modal{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:440px;background:var(--bg-s);border:1px solid var(--bd2);border-radius:12px;z-index:301;display:none;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.5)}
.settings-modal.open{display:flex}
.sm-hdr{padding:16px 20px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between}
.sm-hdr-title{font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px}
.sm-hdr button{background:none;border:none;color:var(--tx2);font-size:16px;cursor:pointer;padding:2px 6px;border-radius:4px}
.sm-hdr button:hover{background:var(--bg-hov);color:var(--tx)}
.sm-body{padding:20px;display:flex;flex-direction:column;gap:14px}
.sm-field{display:flex;flex-direction:column;gap:5px}
.sm-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.07em;text-transform:uppercase}
.sm-lbl small{font-weight:400;text-transform:none;letter-spacing:0;color:var(--tx3)}
.sm-input{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:8px 11px;color:var(--tx);font-size:12.5px;outline:none;transition:border-color .15s;font-family:inherit}
.sm-input:focus{border-color:var(--bd-acc)}
.sm-hint{font-size:10.5px;color:var(--tx3);line-height:1.5}
.sm-foot{padding:14px 20px;border-top:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;gap:12px}
#cfg-msg{font-size:11.5px;flex:1}
#cfg-save{background:var(--acc);color:#fff;border:none;border-radius:7px;padding:8px 18px;font-size:12.5px;font-weight:700;cursor:pointer;white-space:nowrap;flex-shrink:0}
#cfg-save:disabled{opacity:.5;cursor:default}

/* ── STORY BUTTON ── */
.btn-story{padding:7px 14px;background:transparent;color:var(--c-fix);border:1px solid rgba(168,85,247,.35);border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;margin-top:7px}
.btn-story:hover{background:rgba(168,85,247,.1)}

/* ── STORY MODAL ── */
.story-modal{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:460px;background:var(--bg-s);border:1px solid var(--bd2);border-radius:12px;z-index:302;display:none;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.5)}
.story-modal.open{display:flex}
.st-hdr{padding:16px 20px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between}
.st-hdr-title{font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px}
.st-hdr button{background:none;border:none;color:var(--tx2);font-size:16px;cursor:pointer;padding:2px 6px;border-radius:4px}
.st-hdr button:hover{background:var(--bg-hov);color:var(--tx)}
.st-body{padding:20px;display:flex;flex-direction:column;gap:14px}
.st-view{display:none;flex-direction:column;gap:14px}
.st-view.active{display:flex}
.st-analyze-row{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.st-analyze-item{display:flex;gap:8px;font-size:12px}
.st-analyze-lbl{color:var(--tx3);font-weight:600;min-width:60px;flex-shrink:0}
.st-analyze-val{color:var(--tx)}
.st-field{display:flex;flex-direction:column;gap:5px}
.st-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.07em;text-transform:uppercase}
.st-input{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:8px 11px;color:var(--tx);font-size:12.5px;outline:none;transition:border-color .15s;font-family:inherit}
.st-input:focus{border-color:var(--bd-acc)}
.st-md-row{display:flex;align-items:center;gap:10px}
.st-md-input{width:80px;text-align:center}
.st-preview-box{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:12px 14px;font-size:12.5px;color:var(--tx);line-height:1.65;word-break:break-word}
.st-preview-title{font-size:11px;font-weight:700;color:var(--tx3);letter-spacing:.07em;text-transform:uppercase;margin-bottom:6px}
.st-foot{padding:13px 20px;border-top:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;gap:10px}
.st-msg{font-size:11.5px;flex:1}
.btn-st-next{background:var(--acc);color:#fff;border:none;border-radius:7px;padding:8px 16px;font-size:12.5px;font-weight:700;cursor:pointer;flex-shrink:0}
.btn-st-next:disabled{opacity:.5;cursor:default}
.btn-st-back{background:transparent;color:var(--tx2);border:1px solid var(--bd2);border-radius:7px;padding:8px 13px;font-size:12px;font-weight:600;cursor:pointer;flex-shrink:0}

/* ── DATE SEARCH ── */
.ds-date{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:7px 10px;color:var(--tx);font-size:12.5px;outline:none;font-family:inherit;transition:border-color .15s;min-width:130px}
.ds-date:focus{border-color:var(--bd-acc)}
.ds-sep{color:var(--tx3);font-size:12px}
.btn-ds-search{background:var(--acc);color:#fff;border:none;border-radius:7px;padding:7px 16px;font-size:12.5px;font-weight:700;cursor:pointer;white-space:nowrap}
.btn-ds-search:disabled{opacity:.5;cursor:default}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:2px}
::-webkit-scrollbar-thumb:hover{background:var(--tx3)}

/* ── REPORT VIEW ── */
.rpt-page{padding:20px 28px}
.gf-bar{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:14px;background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:11px 16px}
.gf-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.07em;text-transform:uppercase;flex-shrink:0}
.rtabs{display:flex;gap:2px;margin-bottom:16px;background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:4px}
.rtab{flex:1;padding:8px 10px;border:none;background:transparent;color:var(--tx2);font-size:12px;font-weight:600;border-radius:7px;cursor:pointer;transition:all .12s;white-space:nowrap}
.rtab.active{background:var(--bg-s);color:var(--tx);box-shadow:0 1px 4px rgba(0,0,0,.4)}
.rtab:hover:not(.active){color:var(--tx)}
.sum-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.sum-card{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:16px 18px;position:relative;overflow:hidden}
.sum-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2.5px;border-radius:10px 10px 0 0;background:var(--acc)}
.sum-card-warn::before{background:var(--c-crit)}
.sum-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:8px}
.sum-val{font-size:28px;font-weight:900;letter-spacing:-.04em;line-height:1;color:var(--tx)}
.sum-card-warn .sum-val{color:var(--c-crit)}
.sum-desc{font-size:10.5px;color:var(--tx3);margin-top:4px}
.unproc-banner{background:linear-gradient(135deg,rgba(255,68,68,.07),rgba(43,109,255,.07));border:1px dashed rgba(255,68,68,.25);border-radius:10px;padding:13px 18px;display:flex;align-items:center;gap:12px;cursor:pointer;transition:background .12s}
.unproc-banner:hover{background:linear-gradient(135deg,rgba(255,68,68,.12),rgba(43,109,255,.12))}
.unproc-ico{font-size:20px}
.unproc-txt{flex:1;font-size:12.5px;color:var(--tx)}
.banner-arrow{font-size:11px;color:var(--acc);font-weight:700;white-space:nowrap}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.chart-box{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:16px}
.chart-title{font-size:12px;font-weight:700;color:var(--tx2);margin-bottom:12px}
.avg-cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.avg-card{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:13px 18px;min-width:130px}
.avg-card-lbl{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px}
.avg-card-val{font-size:22px;font-weight:900;color:var(--c-ok);letter-spacing:-.03em}
.avg-card-sub{font-size:10.5px;color:var(--tx3);margin-top:3px}
.tcard-hdr{padding:11px 16px;font-size:12px;font-weight:700;color:var(--tx2);border-bottom:1px solid var(--bd)}
.jbadge-yes{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(46,202,138,.12);color:#4cd9a0}
.jbadge-no{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(255,68,68,.12);color:#ff7070}
.jlnk{color:#ffc94d;font-size:11px;font-weight:600}
.jlnk:hover{text-decoration:underline}
.overdue-hi{color:var(--c-crit);font-weight:700}
.overdue-md{color:var(--c-med);font-weight:700}
.overdue-lo{color:var(--tx2);font-weight:600}
.hist-filter{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:10px}
.md-panel{position:fixed;right:0;top:0;bottom:0;width:440px;background:#14274d;border-left:3px solid var(--acc);box-shadow:-8px 0 36px rgba(0,0,0,.7);z-index:305;transform:translateX(100%);transition:transform .22s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden}
.md-panel.open{transform:translateX(0)}
.md-hdr{padding:16px 20px;border-bottom:1px solid var(--bd2);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:10px}
.md-hdr-title{font-size:13.5px;font-weight:700;color:var(--tx);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.md-hdr button{background:rgba(255,255,255,.07);border:none;color:var(--tx2);font-size:15px;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.md-body{flex:1;overflow-y:auto;padding:18px 20px;display:flex;flex-direction:column;gap:10px}
.dp-field{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:8px;padding:9px 11px}
.dp-field-lbl{font-size:10px;color:var(--tx3);margin-bottom:3px;font-weight:600;letter-spacing:.04em}
.dp-field-val{font-size:12px;color:var(--tx);font-weight:500;word-break:break-all}
.dp-body-text{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;font-size:11.5px;color:var(--tx2);line-height:1.65;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto}
.spinner-wrap{display:flex;justify-content:center;padding:36px}
.spin{width:26px;height:26px;border:3px solid var(--bd2);border-top-color:var(--acc);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>

<header class="hdr">
  <div class="hdr-l">
    <div class="logo">M</div>
    <div class="hdr-titles">
      <span class="hdr-co">마스턴투자운용</span>
      <span class="hdr-sys">오류 자동수정 시스템</span>
    </div>
    <div class="hdr-sep"></div>
    <div class="live"><div class="live-dot"></div>LIVE</div>
  </div>
  <div class="hdr-r">
    <span class="last-upd" id="last-upd">갱신 대기 중</span>
    <button class="btn btn-ghost" id="btn-settings" onclick="openSettings()" title="개인 설정" style="padding:5px 10px;font-size:16px;line-height:1">&#9881;</button>
    <span class="clock" id="clock">--:--:--</span>
  </div>
</header>

<div class="wrap">
  <aside class="sb">
    <div class="sb-sec">
      <div class="sb-lbl">모니터링</div>
      <div class="nav-item active" id="nav-today" onclick="showView('today')">
        <svg class="nav-ico" viewBox="0 0 16 16" fill="none">
          <path d="M2 11l3.5-4 3 3L12 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="13.5" cy="11.5" r="2" fill="currentColor"/>
        </svg>
        인바운드 현황
        <span class="nav-cnt" id="crit-cnt" style="display:none">0</span>
      </div>
      <div class="nav-item" style="opacity:.45;pointer-events:none">
        <svg class="nav-ico" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.5"/>
          <path d="M8 5v3l2 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        자동 수정
        <span class="nav-soon">준비중</span>
      </div>
      <div class="nav-item" id="nav-report" onclick="showView('report')">
        <svg class="nav-ico" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
          <path d="M5 7h6M5 10h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        리포트
      </div>
    </div>

    <div class="sb-sec">
      <div class="sb-lbl">분류별 건수</div>
      <div class="sb-cats" id="sb-cats"></div>
    </div>

    <div class="sb-foot">
      <div class="sb-hint">
        <b>자동 갱신</b>
        30초마다 최신 데이터로 자동 갱신됩니다.
        <div class="cdwn" id="cdwn">다음 갱신: 30s</div>
      </div>
    </div>
  </aside>

  <main class="main">
    <div class="main-in" id="today-view">

      <div class="pg-hdr">
        <div>
          <div class="pg-title">인바운드 오류 현황</div>
          <div class="pg-sub" id="pg-sub"></div>
        </div>
        <button class="btn btn-ghost" onclick="fetchAndRender()">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d="M13.5 8A5.5 5.5 0 002.5 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <path d="M2.5 8a5.5 5.5 0 0011 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-dasharray="2 3"/>
            <path d="M13.5 4.5l.5 3.5-3.5-.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          새로고침
        </button>
      </div>

      <div class="stats">
        <div class="scard s-all"><div class="sc-lbl">오늘 전체</div><div class="sc-val" id="st-all">—</div><div class="sc-desc">수신된 인바운드</div></div>
        <div class="scard s-crit"><div class="sc-lbl">긴급</div><div class="sc-val" id="st-crit">—</div><div class="sc-desc">즉시 대응 필요</div></div>
        <div class="scard s-task"><div class="sc-lbl">작업 요청</div><div class="sc-val" id="st-task">—</div><div class="sc-desc">처리 대기 중</div></div>
        <div class="scard s-jira"><div class="sc-lbl">Jira 티켓</div><div class="sc-val" id="st-jira">—</div><div class="sc-desc">자동 생성됨</div></div>
        <div class="scard s-info"><div class="sc-lbl">문의 / 공지</div><div class="sc-val" id="st-info">—</div><div class="sc-desc">참고 처리</div></div>
      </div>

      <div class="frow">
        <div class="srch-wrap">
          <svg class="srch-ico" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10.5 10.5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <input type="text" class="srch" id="srch" placeholder="제목 또는 발신자 검색...">
        </div>
        <select class="fsel" id="sev-sel">
          <option value="">전체 심각도</option>
          <option value="urgent">긴급</option>
          <option value="task">작업요청</option>
          <option value="inquiry">문의</option>
          <option value="project">프로젝트</option>
          <option value="info">공지</option>
          <option value="spam">스팸</option>
          <option value="unknown">미분류</option>
        </select>
        <div class="ftabs">
          <div class="ftab active" data-src="all">전체</div>
          <div class="ftab" data-src="outlook">Outlook</div>
          <div class="ftab" data-src="teams">Teams</div>
        </div>
        <span style="color:var(--tx3);font-size:12px;padding:0 2px">|</span>
        <input type="date" class="ds-date" id="ds-start">
        <span class="ds-sep">~</span>
        <input type="date" class="ds-date" id="ds-end">
        <button class="btn-ds-search" onclick="runDateSearch()">검색</button>
        <button class="btn btn-ghost" onclick="resetToToday()" style="font-size:12.5px;padding:8px 16px">오늘</button>
        <button class="btn btn-ghost" onclick="setDsRange('week')" style="font-size:12.5px;padding:8px 16px">이번 주</button>
        <button class="btn btn-ghost" onclick="setDsRange('month')" style="font-size:12.5px;padding:8px 16px">이번 달</button>
      </div>

      <div class="banner">
        <div class="banner-ico">🤖</div>
        <div class="banner-tx">
          <strong>자동 수정 엔진 연동 준비 중</strong>
          인바운드 분류 단계 완료. 오류 패턴 학습 후 자동 수정 파이프라인이 활성화됩니다.
        </div>
      </div>

      <div class="tcard">
        <div class="twrap">
          <table>
            <thead id="main-thead">
              <tr>
                <th class="sortable" data-col="id" onclick="sortBy('id')">ID</th>
                <th class="sortable" data-col="source" onclick="sortBy('source')">출처</th>
                <th class="sortable" data-col="subject" onclick="sortBy('subject')">제목</th>
                <th class="sortable" data-col="sender" onclick="sortBy('sender')">발신자</th>
                <th class="sortable" data-col="intent_type" onclick="sortBy('intent_type')">분류</th>
                <th class="sortable" data-col="personal_priority" onclick="sortBy('personal_priority')">중요도</th>
                <th class="sortable" data-col="email_category" onclick="sortBy('email_category')">카테고리</th>
                <th class="sortable" data-col="action_required" onclick="sortBy('action_required')">액션</th>
                <th class="sortable sort-desc" data-col="received_at" onclick="sortBy('received_at')">수신 시각</th>
                <th class="sortable" data-col="jira_key" onclick="sortBy('jira_key')">Jira</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="tbody"><tr><td colspan="11" class="empty">데이터를 불러오는 중...</td></tr></tbody>
          </table>
        </div>
      </div>

    </div><!-- /main-in -->
    <div id="report-view" style="display:none">
      <div class="rpt-page">

        <!-- 공통 날짜 필터 -->
        <div class="gf-bar">
          <span class="gf-lbl">조회 기간</span>
          <input type="date" class="ds-date" id="r-start">
          <span class="ds-sep">~</span>
          <input type="date" class="ds-date" id="r-end">
          <button class="btn-ds-search" onclick="doSearch()">검색</button>
          <button class="btn btn-ghost" onclick="setRange('today')">오늘</button>
          <button class="btn btn-ghost" onclick="setRange('week')">이번 주</button>
          <button class="btn btn-ghost" onclick="setRange('month')">이번 달</button>
        </div>

        <!-- 탭 네비게이션 -->
        <div class="rtabs" id="rtabs">
          <button class="rtab active" onclick="switchRptTab('home')">&#127968; 대시보드</button>
          <button class="rtab" onclick="switchRptTab('mail')">&#128139; 메일 수신 현황</button>
          <button class="rtab" onclick="switchRptTab('jira')">&#127993; Jira 티켓 현황</button>
          <button class="rtab" onclick="switchRptTab('history')">&#128203; 처리 이력</button>
        </div>

        <!-- 탭1: 대시보드 -->
        <div class="tab-pane" id="tab-home">
          <div class="sum-cards">
            <div class="sum-card">
              <div class="sum-lbl" id="sum-mail-lbl">오늘 수신 메일</div>
              <div class="sum-val" id="sum-mail">&#8212;</div>
              <div class="sum-desc">총 수신 건수</div>
            </div>
            <div class="sum-card">
              <div class="sum-lbl" id="sum-jira-lbl">오늘 Jira 등록</div>
              <div class="sum-val" id="sum-jira">&#8212;</div>
              <div class="sum-desc">자동 생성 티켓</div>
            </div>
            <div class="sum-card">
              <div class="sum-lbl" id="sum-rate-lbl">이번 주 처리율</div>
              <div class="sum-val" id="sum-rate">&#8212;</div>
              <div class="sum-desc">메일 대비 Jira 등록률</div>
            </div>
            <div class="sum-card sum-card-warn">
              <div class="sum-lbl">&#9888; 기한 초과</div>
              <div class="sum-val" id="sum-overdue">&#8212;</div>
              <div class="sum-desc">즉시 확인 필요</div>
            </div>
          </div>
          <div class="unproc-banner" onclick="switchRptTab('mail')">
            <span class="unproc-ico">&#128365;</span>
            <span class="unproc-txt" id="unproc-txt">미처리 데이터 로딩 중...</span>
            <span class="banner-arrow">&#8594; 메일 수신 현황</span>
          </div>
        </div>

        <!-- 탭2: 메일 수신 현황 -->
        <div class="tab-pane" id="tab-mail" style="display:none">
          <div class="chart-row">
            <div class="chart-box">
              <div class="chart-title">팀/부서별 수신 건수</div>
              <canvas id="chart-team-mail" height="220"></canvas>
              <div id="empty-team-mail" class="empty" style="display:none">데이터가 없습니다</div>
            </div>
            <div class="chart-box">
              <div class="chart-title">월별 수신 추이</div>
              <canvas id="chart-monthly" height="220"></canvas>
              <div id="empty-monthly" class="empty" style="display:none">데이터가 없습니다</div>
            </div>
          </div>
          <div class="tcard">
            <div class="twrap">
              <table>
                <thead id="mail-thead"><tr>
                  <th class="sortable sort-desc" data-col="received_at" onclick="sortMailBy('received_at')">수신일시</th>
                  <th class="sortable" data-col="sender" onclick="sortMailBy('sender')">발신자</th>
                  <th class="sortable" data-col="subject" onclick="sortMailBy('subject')">제목</th>
                  <th class="sortable" data-col="has_jira" onclick="sortMailBy('has_jira')">Jira</th>
                </tr></thead>
                <tbody id="mail-tbody"><tr><td colspan="4" class="spinner-wrap"><div class="spin"></div></td></tr></tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- 탭3: Jira 티켓 현황 -->
        <div class="tab-pane" id="tab-jira" style="display:none">
          <div class="avg-cards" id="avg-cards"></div>
          <div class="chart-row" style="margin-bottom:0">
            <div class="chart-box">
              <div class="chart-title">상태별 현황</div>
              <canvas id="chart-jira-status" height="260"></canvas>
              <div id="empty-jira-status" class="empty" style="display:none">데이터가 없습니다</div>
            </div>
            <div class="chart-box">
              <div class="chart-title">팀별 요청 건수 (내림차순)</div>
              <canvas id="chart-jira-team" height="260"></canvas>
              <div id="empty-jira-team" class="empty" style="display:none">데이터가 없습니다</div>
            </div>
          </div>
          <div class="tcard">
            <div class="tcard-hdr">&#9888;&#65039; 기한 초과 목록</div>
            <div class="twrap">
              <table>
                <thead><tr><th>티켓번호</th><th>제목</th><th>기한</th><th>초과일수</th></tr></thead>
                <tbody id="overdue-tbody"><tr><td colspan="4" class="spinner-wrap"><div class="spin"></div></td></tr></tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- 탭4: 처리 이력 -->
        <div class="tab-pane" id="tab-history" style="display:none">
          <div class="hist-filter">
            <input type="text" class="srch" id="h-search" placeholder="발신자 또는 제목 검색...">
            <select class="fsel" id="h-team"><option value="">전체 팀</option></select>
            <select class="fsel" id="h-status">
              <option value="">전체 상태</option>
              <option value="jira">등록완료</option>
              <option value="no_jira">미등록</option>
            </select>
            <button class="btn-ds-search" onclick="loadHistory()">필터 적용</button>
            <button class="btn btn-ghost" style="margin-left:auto" onclick="exportCsv()">&#128190; 엑셀 다운로드</button>
          </div>
          <div class="tcard" style="margin-top:0">
            <div class="twrap">
              <table>
                <thead><tr><th>날짜</th><th>발신자</th><th>팀</th><th>제목</th><th>Jira 티켓</th><th>소요 시간</th></tr></thead>
                <tbody id="hist-tbody"><tr><td colspan="6" class="spinner-wrap"><div class="spin"></div></td></tr></tbody>
              </table>
            </div>
          </div>
        </div>

      </div><!-- /rpt-page -->
    </div><!-- /report-view -->

    <!-- 리포트 메일 상세 패널 -->
    <div class="modal-ov" id="md-ov" onclick="closeMd()"></div>
    <div class="md-panel" id="md-panel">
      <div class="md-hdr">
        <span class="md-hdr-title" id="md-title">메일 상세</span>
        <button onclick="closeMd()">&#10005;</button>
      </div>
      <div class="md-body">
        <div class="dp-field"><div class="dp-field-lbl">발신자</div><div class="dp-field-val" id="md-sender"></div></div>
        <div class="dp-field"><div class="dp-field-lbl">수신일시</div><div class="dp-field-val" id="md-date"></div></div>
        <div class="dp-field"><div class="dp-field-lbl">Jira 티켓</div><div class="dp-field-val" id="md-jira">&#8212;</div></div>
        <div>
          <div style="font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.04em;margin-bottom:6px">본문</div>
          <div class="dp-body-text" id="md-body">로딩 중...</div>
        </div>
      </div>
    </div>

  </main>
</div>

<div class="modal-ov" id="settings-ov" onclick="closeSettings()"></div>
<div class="settings-modal" id="settings-modal">
  <div class="sm-hdr">
    <div class="sm-hdr-title">&#9881; 개인 설정</div>
    <button onclick="closeSettings()">&#10005;</button>
  </div>
  <div class="sm-body">
    <div class="sm-field">
      <label class="sm-lbl">이름</label>
      <input id="cfg-name" class="sm-input" type="text" placeholder="예: 홍길동">
    </div>
    <div class="sm-field">
      <label class="sm-lbl">내 이메일 주소 <small>(쉼표로 구분)</small></label>
      <input id="cfg-email" class="sm-input" type="text" placeholder="예: me@company.com,me2@company.com">
      <div class="sm-hint">이 주소로 수신된 메일을 "나에게 온 메일"로 판단합니다.</div>
    </div>
    <div class="sm-field">
      <label class="sm-lbl">업무 키워드 <small>(쉼표로 구분)</small></label>
      <input id="cfg-keywords" class="sm-input" type="text" placeholder="예: GW,그룹웨어,전자결재">
      <div class="sm-hint">LLM이 내 업무 관련성을 판단하는 기준이 됩니다.</div>
    </div>
    <div class="sm-field" style="border-top:1px solid var(--bd);padding-top:12px">
      <label class="sm-lbl">Jira 티켓 자동 생성</label>
      <label style="display:flex;align-items:center;gap:9px;cursor:pointer;padding:6px 0">
        <input type="checkbox" id="cfg-jira-auto" style="width:15px;height:15px;accent-color:var(--acc);cursor:pointer">
        <span style="font-size:12px;color:var(--tx2)">긴급·작업 메일 수신 시 즉시 자동 생성</span>
      </label>
      <div class="sm-hint">체크 해제 시 JIRA_ENABLED=true여도 수동으로만 생성됩니다.</div>
    </div>
    <div class="sm-field">
      <label class="sm-lbl">스토리 Epic Key <small>(등록 위치)</small></label>
      <input id="cfg-epic-key" class="sm-input" type="text" placeholder="예: GW-5">
      <div class="sm-hint">스토리를 등록할 Epic Key. 비어 있으면 Epic 연결 없이 생성됩니다.</div>
    </div>
    <div class="sm-field">
      <label class="sm-lbl">스토리 스프린트 이름</label>
      <input id="cfg-sprint-name" class="sm-input" type="text" placeholder="예: 2026 디지털혁신본부 업무">
      <div class="sm-hint">정확한 스프린트 이름을 입력하세요. 일치하지 않으면 스프린트 없이 생성됩니다.</div>
    </div>
    <div class="sm-field" style="border-top:1px solid var(--bd);padding-top:12px">
      <label class="sm-lbl">Jira 계정 ID <small>(담당자·보고자용)</small></label>
      <input id="cfg-account-id" class="sm-input" type="text" placeholder="Server: 로그인ID  /  Cloud: accountId">
      <div class="sm-hint">Server: Jira 로그인 아이디 (예: bae.heuju)<br>Cloud (.atlassian.net): REST API /myself 응답의 accountId 값</div>
    </div>
  </div>
  <div class="sm-foot">
    <div id="cfg-msg"></div>
    <button id="cfg-save" onclick="saveSettings()">저장</button>
  </div>
</div>

<div class="modal-ov" id="story-ov" onclick="closeStoryModal()"></div>
<div class="story-modal" id="story-modal">
  <div class="st-hdr">
    <div class="st-hdr-title">&#128221; Jira &#49828;&#53664;&#47532; &#51089;&#49457;</div>
    <button onclick="closeStoryModal()">&#10005;</button>
  </div>
  <div class="st-body">
    <div class="st-view active" id="st-view1">
      <div id="st-analyzing" style="font-size:12px;color:var(--tx3)">LLM&#51004;&#47196; &#47700;&#51068; &#48516;&#49437; &#51473;...</div>
      <div id="st-analyze-result" style="display:none">
        <div class="st-analyze-row" id="st-analyze-box"></div>
      </div>
      <div class="st-field" id="st-field-team" style="display:none">
        <label class="st-lbl">요청 팀</label>
        <input id="st-team" class="st-input" type="text" placeholder="예: 그룹웨어팀">
      </div>
      <div class="st-field" id="st-field-task" style="display:none">
        <label class="st-lbl">핵심 업무</label>
        <input id="st-task" class="st-input" type="text" placeholder="예: 전자결재 모바일 연동 개발">
      </div>
    </div>
    <div class="st-view" id="st-view2">
      <div class="st-field">
        <label class="st-lbl">&#50696;&#49345; &#49548;&#50836;&#51068;&#49688; (M/D)</label>
        <div class="st-md-row">
          <input id="st-md" class="st-input st-md-input" type="number" min="0.25" step="0.25" value="1">
          <span style="font-size:12px;color:var(--tx2)">M/D</span>
        </div>
      </div>
      <div class="st-field">
        <label class="st-lbl">레이블 <small style="color:var(--tx3);text-transform:none;letter-spacing:0">(쉼표로 구분)</small></label>
        <input id="st-labels" class="st-input" type="text" placeholder="예: frontend, Q2-2026">
      </div>
      <div style="display:flex;gap:10px">
        <div class="st-field" style="flex:1">
          <label class="st-lbl">시작일</label>
          <input id="st-start-date" class="st-input" type="date">
        </div>
        <div class="st-field" style="flex:1">
          <label class="st-lbl">기한</label>
          <input id="st-due-date" class="st-input" type="date">
        </div>
      </div>
      <div class="st-field">
        <label class="st-lbl">우선순위</label>
        <div id="st-priority-badge" style="font-size:12px;padding:4px 0"></div>
      </div>
      <div class="st-field">
        <label class="st-lbl">스토리 제목 <small style="color:var(--tx3);text-transform:none;letter-spacing:0">(직접 수정 가능)</small></label>
        <textarea id="st-preview-title-box" class="st-input" rows="2" style="resize:vertical;line-height:1.55">&#8212;</textarea>
      </div>
    </div>
  </div>
  <div class="st-foot">
    <span class="st-msg" id="st-msg"></span>
    <button class="btn-st-back" id="btn-st-back" onclick="storyBack()" style="display:none">&#8592; &#51060;&#51204;</button>
    <button class="btn-st-next" id="btn-st-next" onclick="storyNext()">&#45796;&#51020;</button>
  </div>
</div>

<div class="ov" id="ov" onclick="closeDetail()"></div>
<div class="dp" id="dp">
  <div class="dp-hdr">
    <div class="dp-hdr-l">
      <div class="dp-id" id="dp-id"></div>
      <div class="dp-title" id="dp-title"></div>
    </div>
    <button class="dp-close" onclick="closeDetail()">&#10005;</button>
  </div>
  <div class="dp-body">
    <div>
      <div class="dp-sec-lbl">오류 정보</div>
      <div class="dp-grid">
        <div class="dp-field"><div class="dp-field-lbl">심각도</div><div class="dp-field-val" id="dp-sev"></div></div>
        <div class="dp-field"><div class="dp-field-lbl">출처</div><div class="dp-field-val" id="dp-src"></div></div>
        <div class="dp-field"><div class="dp-field-lbl">발신자</div><div class="dp-field-val" id="dp-sender"></div></div>
        <div class="dp-field"><div class="dp-field-lbl">수신 시각</div><div class="dp-field-val" id="dp-time"></div></div>
      </div>
    </div>
    <div id="dp-personal-sec" style="display:none">
      <div class="dp-sec-lbl">개인 중요도</div>
      <div class="dp-grid">
        <div class="dp-field"><div class="dp-field-lbl">중요도</div><div class="dp-field-val" id="dp-pp"></div></div>
        <div class="dp-field"><div class="dp-field-lbl">카테고리</div><div class="dp-field-val" id="dp-ec"></div></div>
        <div class="dp-field"><div class="dp-field-lbl">액션 필요</div><div class="dp-field-val" id="dp-ar"></div></div>
        <div class="dp-field" id="dp-action-field" style="display:none"><div class="dp-field-lbl">권장 액션</div><div class="dp-field-val" id="dp-suggested"></div></div>
      </div>
    </div>
    <div id="dp-edit-sec">
      <div class="dp-sec-lbl">분류 수정</div>
      <div class="dp-edit-grid">
        <div class="dp-edit-row">
          <label class="dp-field-lbl">분류</label>
          <select class="dp-select" id="dp-edit-intent">
            <option value="urgent">긴급</option>
            <option value="task">작업요청</option>
            <option value="inquiry">문의</option>
            <option value="project">프로젝트</option>
            <option value="info">공지</option>
            <option value="spam">스팸</option>
            <option value="unknown">미분류</option>
          </select>
        </div>
        <div class="dp-edit-row">
          <label class="dp-field-lbl">중요도</label>
          <select class="dp-select" id="dp-edit-priority">
            <option value="">&#8212;</option>
            <option value="high">HIGH</option>
            <option value="medium">MED</option>
            <option value="low">LOW</option>
          </select>
        </div>
        <div class="dp-edit-row">
          <label class="dp-field-lbl">카테고리</label>
          <select class="dp-select" id="dp-edit-category">
            <option value="">&#8212;</option>
            <option value="긴급처리">긴급처리</option>
            <option value="내업무">내업무</option>
            <option value="참조">참조</option>
            <option value="무시">무시</option>
          </select>
        </div>
        <div class="dp-edit-row">
          <label class="dp-field-lbl">권장 액션</label>
          <input class="dp-text-input" id="dp-edit-action" type="text" placeholder="액션 입력...">
        </div>
      </div>
      <button class="btn-save-meta" onclick="saveMetaEdit()">저장</button>
      <span class="dp-save-msg" id="dp-save-msg"></span>
    </div>
    <div id="dp-body-sec">
      <div class="dp-sec-lbl">메일 본문</div>
      <div class="dp-body-text" id="dp-body-content">불러오는 중...</div>
    </div>
    <div id="dp-jira-sec">
      <div class="dp-sec-lbl">Jira 티켓</div>
      <div id="dp-jira-existing" style="display:none">
        <div class="dp-field"><div class="dp-field-lbl">티켓 키</div><div class="dp-field-val"><a id="dp-jira-lnk" href="#" target="_blank" class="jlnk"></a></div></div>
      </div>
      <div id="dp-jira-create" style="display:none">
        <button class="btn-jira" id="btn-create-jira" onclick="createJiraManually()">&#127931; Jira 작업 자동 생성</button>
        <button class="btn-story" id="btn-create-story" onclick="openStoryModal()" style="display:none">&#128221; Jira 스토리 작성</button>
        <div id="dp-jira-msg" style="font-size:11px;margin-top:6px;color:var(--tx3)"></div>
      </div>

    </div>
    <div id="dp-ea-sec">
      <div class="dp-sec-lbl">오류 분석</div>
      <button class="btn-analyze" id="btn-analyze" onclick="runErrorAnalysis()">&#128269; AI 오류 분석</button>
      <div class="ea-result" id="ea-result" style="display:none"></div>
    </div>
    <div>
      <div class="dp-sec-lbl">자동 수정 파이프라인</div>
      <div class="af-card">
        <div class="af-hdr">
          <div class="af-title">&#9889; 자동 수정 상태</div>
          <span class="af-badge" id="dp-af-badge">분류 완료</span>
        </div>
        <div class="af-steps">
          <div class="af-step"><div class="step-ic ic-done">&#10003;</div><span class="lbl-done">인바운드 수신 &amp; 분류</span></div>
          <div class="af-step"><div class="step-ic ic-done">&#10003;</div><span class="lbl-done">우선순위 판정</span></div>
          <div class="af-step"><div class="step-ic ic-done">&#10003;</div><span class="lbl-done">원인 분석</span></div>
          <div class="af-step"><div class="step-ic ic-pend">4</div><span class="lbl-pend">자동 수정 실행 (준비 중)</span></div>
          <div class="af-step"><div class="step-ic ic-pend">5</div><span class="lbl-pend">수정 결과 검증 (준비 중)</span></div>
        </div>
        <div class="af-prog"><div class="af-fill" id="dp-prog" style="width:60%"></div></div>
      </div>
    </div>
  </div>
  <div style="padding:10px 16px 0;display:flex;justify-content:flex-end">
    <button class="btn-delete" id="btn-delete-msg" onclick="deleteMessage()">&#128465; 삭제</button>
  </div>
  <div class="dp-foot"><div class="dp-foot-tx" id="dp-foot"></div></div>
</div>

<script>
const JIRA_BASE = "https://mastern.atlassian.net/browse/";

function cleanBody(raw) {
  if (!raw) return "(본문 없음)";
  // HTML 제거
  if (raw.includes("<") && raw.includes(">")) {
    try {
      const doc = new DOMParser().parseFromString(raw, "text/html");
      raw = doc.body.textContent || "";
    } catch(e) {}
  }
  // 줄바꿈 정규화
  raw = raw.replace(/\\r\\n|\\r/g, "\\n");
  // 푸터 탐지 후 절삭
  const FOOTER_RE = /(copyright|©\\s*\\d{4}|개인정보\\s*보호정책|알림\\s*관리|수신거부|unsubscribe|이\\s*(이메일|메시지)을?\\s*더\\s*이상|문의처\\s*[:：]|고객\\s*센터\\s*[:：])/i;
  const allLines = raw.split("\\n");
  let cutAt = allLines.length;
  for (let i = 0; i < allLines.length; i++) { if (FOOTER_RE.test(allLines[i])) { cutAt = i; break; } }
  const bodyLines = allLines.slice(0, cutAt);
  // 메타/구분선/시스템 줄 필터
  const RE_META = /^(보낸\\s*사람|받는\\s*사람|참조|From|To|CC|Sent|Date|Subject|날짜|제목)\\s*[:：]/i;
  const RE_SEP  = /^[-=_*#]{4,}\\s*$/;
  const RE_QH   = /님이\\s*작성|wrote\\s*:/i;
  const RE_SYS  = /^(대한민국\\s*시간|Attached\\s+file|회신\\s*:)/i;
  const RE_FILE = /\\.(pdf|docx?|xlsx?|pptx?|hwp|zip|png|jpg|gif|txt|csv)\\s*$/i;
  const attachFiles = [], filtered = [];
  for (const line of bodyLines) {
    const t = line.trim();
    if (!t) { filtered.push(""); continue; }
    if (RE_SEP.test(t) || RE_META.test(t) || RE_QH.test(t) || RE_SYS.test(t)) continue;
    if (RE_FILE.test(t) && t.length < 120) { attachFiles.push(t); continue; }
    filtered.push(t);
  }
  // 연속 중복/빈 줄 정리
  const deduped = [];
  for (let i = 0; i < filtered.length; i++) {
    if (!filtered[i] && (!deduped.length || deduped[deduped.length-1] === "")) continue;
    if (filtered[i] && i > 0 && filtered[i] === filtered[i-1]) continue;
    deduped.push(filtered[i]);
  }
  const cleanText = deduped.join("\\n").replace(/\\n{3,}/g, "\\n\\n").trim();
  // 날짜 파싱
  function parseKorDate(s) {
    const yr = (s.match(/(\\d{4})\\s*[년.]/) || [])[1] || new Date().getFullYear();
    const mo = (s.match(/(\\d{1,2})\\s*[월.]/) || [])[1];
    const dy = (s.match(/(\\d{1,2})\\s*[일.]/) || [])[1];
    if (!mo || !dy) return null;
    return new Date(+yr, +mo - 1, +dy);
  }
  function isOverdue(d) { return d && d < new Date(new Date().setHours(0,0,0,0)); }
  // Jira 티켓 추출
  const tickets = [...new Set([...cleanText.matchAll(/([A-Z]{2,10}-\\d+)/g)].map(m => m[1]))];
  // 기한 추출
  let dueDate = null, dueDateStr = null;
  for (const line of deduped) {
    const dm = line.match(/(?:기한|마감|Due\\s*[Dd]ate?)\\s*[:：]\\s*([^\\n]+)/i);
    if (dm) { const d = parseKorDate(dm[1]); if (d) { dueDate = d; dueDateStr = dm[1].trim(); break; } }
  }
  // 수신자 헤더
  const hdr = _userName ? "수신자 : " + _userName + "\\n\\n" : "";
  // Jira 알림 이메일 → 구조화 출력
  if (tickets.length > 0) {
    const ovd = isOverdue(dueDate);
    const out = ["내용 :"];
    if (ovd) out.push("- 기한 초과 업무 " + tickets.length + "건 발생");
    for (const tk of tickets) {
      const tl = deduped.find(l => l.includes(tk)) || tk;
      out.push((ovd ? "⚠️ " : "- ") + tl.trim());
    }
    if (dueDateStr) out.push("- 기한 : " + dueDateStr + (isOverdue(dueDate) ? " (초과)" : ""));
    return hdr + out.join("\\n");
  }
  // 일반 이메일 → 정리된 본문
  let result = hdr + cleanText;
  if (attachFiles.length) result += "\\n\\n[첨부파일]\\n" + attachFiles.map((f,i)=>(i+1)+". "+f).join("\\n");
  return result || "(본문 없음)";
}

const SEV = {
  urgent:  { cls:"sv-crit", lbl:"긴급" },
  task:    { cls:"sv-high", lbl:"작업요청" },
  inquiry: { cls:"sv-med",  lbl:"문의" },
  project: { cls:"sv-med",  lbl:"프로젝트" },
  info:    { cls:"sv-info", lbl:"공지" },
  spam:    { cls:"sv-spam", lbl:"스팸" },
  unknown: { cls:"sv-unk",  lbl:"미분류" },
};

let _data = [], _src = "all", _selId = null, _cdwn = 30, _jiraEnabled = false, _jiraAuto = false, _userName = "";
let _sortCol = "received_at", _sortDir = "desc";

fetch("/dashboard/config").then(r=>r.json()).then(c=>{ _jiraEnabled = !!c.jira_enabled; _jiraAuto = !!c.jira_auto_create; _userName = c.user_name || ""; }).catch(()=>{});

function esc(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

function fmtTime(iso){
  if(!iso) return "-";
  const d = new Date(iso);
  if(isNaN(d)) return "-";
  const p2 = n => String(n).padStart(2,"0");
  return p2(d.getMonth()+1)+"/"+p2(d.getDate())+" "+p2(d.getHours())+":"+p2(d.getMinutes());
}

function fmtFull(iso){
  if(!iso) return "-";
  const d = new Date(iso);
  if(isNaN(d)) return "-";
  const p2 = n => String(n).padStart(2,"0");
  return d.getFullYear()+"."+p2(d.getMonth()+1)+"."+p2(d.getDate())+" "+p2(d.getHours())+":"+p2(d.getMinutes())+":"+p2(d.getSeconds());
}

function sevBadge(k){ const s=SEV[k]||SEV.unknown; return '<span class="sv '+s.cls+'"><span class="sv-dot"></span>'+s.lbl+'</span>'; }

function srcBadge(s){
  if(s==="teams") return '<span class="src src-tm">Teams</span>';
  return '<span class="src src-ol">Outlook</span>';
}

function stBadge(m){
  if(m.jira_key) return '<span class="st st-jira">&#127931; Jira 생성됨</span>';
  if((m.intent_type||"unknown")==="urgent") return '<span class="st st-urg"><span class="st-pulse"></span>대응 필요</span>';
  return '<span class="st st-new">신규 접수</span>';
}

function ppBadge(v){
  if(v==="high")   return '<span class="pp pp-high">HIGH</span>';
  if(v==="medium") return '<span class="pp pp-med">MED</span>';
  if(v==="low")    return '<span class="pp pp-low">LOW</span>';
  return '<span class="pp pp-none">&#8212;</span>';
}

function ecBadge(v){
  if(v==="긴급처리") return '<span class="ec ec-urg">긴급처리</span>';
  if(v==="내업무")   return '<span class="ec ec-mine">내업무</span>';
  if(v==="참조")     return '<span class="ec ec-ref">참조</span>';
  if(v==="무시")     return '<span class="ec ec-ign">무시</span>';
  return '<span class="ec ec-none">&#8212;</span>';
}

function arBadge(v){
  if(v===true)  return '<span class="ar-y">&#10003; 필요</span>';
  if(v===false) return '<span class="ar-n">불필요</span>';
  return '<span class="pp pp-none">&#8212;</span>';
}

function filtered(){
  const q = (document.getElementById("srch").value||"").toLowerCase();
  const sev = document.getElementById("sev-sel").value;
  return _data.filter(m => {
    if(_src!=="all" && m.source!==_src) return false;
    if(sev && (m.intent_type||"unknown")!==sev) return false;
    if(q){
      const hay = ((m.subject||"")+" "+(m.sender||"")).toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });
}

function sortBy(col){
  if(_sortCol===col) _sortDir=_sortDir==="desc"?"asc":"desc";
  else{_sortCol=col;_sortDir="desc";}
  document.querySelectorAll("#main-thead th.sortable").forEach(th=>{
    th.classList.remove("sort-asc","sort-desc");
    if(th.dataset.col===col) th.classList.add(_sortDir==="desc"?"sort-desc":"sort-asc");
  });
  renderTable();
}

function renderTable(){
  const tb = document.getElementById("tbody");
  const rows = filtered();
  rows.sort((a,b)=>{
    const av=String(a[_sortCol]??""), bv=String(b[_sortCol]??"");
    const cmp=av<bv?-1:av>bv?1:0;
    return _sortDir==="asc"?cmp:-cmp;
  });
  if(!rows.length){
    tb.innerHTML = '<tr><td colspan="11" class="empty">표시할 데이터가 없습니다.</td></tr>';
    return;
  }
  tb.innerHTML = rows.map(m => {
    const sel = m.id===_selId ? ' sel' : '';
    const jiraCell = m.jira_key
      ? '<a class="jlnk" href="'+JIRA_BASE+esc(m.jira_key)+'" target="_blank">'+esc(m.jira_key)+'</a>'
      : '<span style="color:var(--tx3)">&#8212;</span>';
    return '<tr class="'+sel+'" data-id="'+esc(m.id)+'">'
      +'<td class="t-id">#'+(m.id||"").slice(0,7).toUpperCase()+'</td>'
      +'<td>'+srcBadge(m.source)+'</td>'
      +'<td class="t-sub">'+esc(m.subject||"(제목 없음)")+'</td>'
      +'<td class="t-snd">'+esc(m.sender||"-")+'</td>'
      +'<td>'+sevBadge(m.intent_type||"unknown")+'</td>'
      +'<td>'+ppBadge(m.personal_priority||null)+'</td>'
      +'<td>'+ecBadge(m.email_category||null)+'</td>'
      +'<td>'+arBadge(m.action_required)+'</td>'
      +'<td class="t-time">'+fmtTime(m.received_at)+'</td>'
      +'<td>'+jiraCell+'</td>'
      +'<td style="text-align:center;padding:6px 8px"><button class="btn-row-del" title="삭제" onclick="rowDeleteMessage(event,this.dataset.id)" data-id="'+esc(m.id)+'">&#128465;</button></td>'
      +'</tr>';
  }).join("");
}

function updateStats(d){
  const cnt = k => d.filter(m=>(m.intent_type||"unknown")===k).length;
  document.getElementById("st-all").textContent  = d.length;
  document.getElementById("st-crit").textContent = cnt("urgent");
  document.getElementById("st-task").textContent = cnt("task");
  document.getElementById("st-jira").textContent = d.filter(m=>m.jira_key).length;
  document.getElementById("st-info").textContent = d.filter(m=>["info","inquiry"].includes(m.intent_type)).length;
  const cc = cnt("urgent");
  const nb = document.getElementById("crit-cnt");
  nb.textContent = cc; nb.style.display = cc>0 ? "inline-block" : "none";
  const cats = document.getElementById("sb-cats");
  const counts = {};
  d.forEach(m=>{ const k=m.intent_type||"unknown"; counts[k]=(counts[k]||0)+1; });
  cats.innerHTML = Object.entries(SEV).map(([k,v])=>{
    const n = counts[k]||0;
    const col = n>0?"var(--tx)":"var(--tx3)";
    return '<div class="sb-cat"><span class="sb-cat-name">'+v.lbl+'</span><span class="sb-cat-n" style="color:'+col+'">'+n+'</span></div>';
  }).join("");
}

async function fetchAndRender(){
  try{
    const start = (document.getElementById("ds-start")||{value:""}).value;
    const end   = (document.getElementById("ds-end")||{value:""}).value;
    const todayStr = new Date().toLocaleDateString("sv-SE");
    const isToday  = !start || (start === todayStr && end === todayStr);
    const url = isToday
      ? "/dashboard/data"
      : "/dashboard/search?start="+encodeURIComponent(start)+"&end="+encodeURIComponent(end);
    const res = await fetch(url);
    _data = await res.json();
    updateStats(_data);
    renderTable();
    const sub = document.getElementById("pg-sub");
    if(isToday){
      const d = new Date();
      sub.textContent = d.toLocaleDateString("ko-KR",{year:"numeric",month:"long",day:"numeric",weekday:"long"})+" 기준 | 실시간 오류 인바운드 현황";
    } else {
      sub.textContent = start+" ~ "+end+" 기간 검색 결과 · 총 "+_data.length+"건";
    }
    document.getElementById("last-upd").textContent = "갱신: "+fmtTime(new Date().toISOString());
    _cdwn = 30;
  }catch(e){ console.error(e); }
}

function openDetail(id){
  const m = _data.find(x=>x.id===id);
  if(!m) return;
  _selId = id;
  renderTable();
  document.getElementById("dp-id").textContent = "#"+(m.id||"").slice(0,10).toUpperCase()+" · "+(m.source||"").toUpperCase();
  document.getElementById("dp-title").textContent = m.subject||"(제목 없음)";
  document.getElementById("dp-sev").innerHTML = sevBadge(m.intent_type||"unknown");
  document.getElementById("dp-src").innerHTML = srcBadge(m.source);
  document.getElementById("dp-sender").textContent = m.sender||"-";
  document.getElementById("dp-time").textContent = fmtFull(m.received_at);
  const ps = document.getElementById("dp-personal-sec");
  if(m.personal_priority || m.email_category || m.action_required !== null){
    ps.style.display="";
    document.getElementById("dp-pp").innerHTML = ppBadge(m.personal_priority||null);
    document.getElementById("dp-ec").innerHTML = ecBadge(m.email_category||null);
    document.getElementById("dp-ar").innerHTML = arBadge(m.action_required);
    const af = document.getElementById("dp-action-field");
    if(m.suggested_action){ af.style.display=""; document.getElementById("dp-suggested").textContent=m.suggested_action; }
    else { af.style.display="none"; }
  } else { ps.style.display="none"; }
  const jiraExisting = document.getElementById("dp-jira-existing");
  const jiraCreate = document.getElementById("dp-jira-create");
  const jiraMsg = document.getElementById("dp-jira-msg");
  const storyBtn = document.getElementById("btn-create-story");
  if(m.jira_key){
    jiraExisting.style.display="";
    jiraCreate.style.display="none";
    storyBtn.style.display="none";
    const lnk = document.getElementById("dp-jira-lnk");
    lnk.textContent = m.jira_key;
    lnk.href = JIRA_BASE+m.jira_key;
  } else {
    jiraExisting.style.display="none";
    jiraCreate.style.display="";
    jiraMsg.textContent="";
    const btn = document.getElementById("btn-create-jira");
    btn.disabled=false;
    btn.textContent = _jiraEnabled ? "📋 Jira 티켓 생성" : "📋 설명 복사";
    storyBtn.style.display = _jiraEnabled ? "" : "none";
  }
  const badge = document.getElementById("dp-af-badge");
  if((m.intent_type||"unknown")==="urgent"){
    badge.textContent="대응 필요"; badge.className="af-badge urg";
  } else {
    badge.textContent="분류 완료"; badge.className="af-badge done";
  }
  // 본문 비동기 로딩
  const bodyEl = document.getElementById("dp-body-content");
  bodyEl.textContent = "불러오는 중...";
  fetch("/dashboard/message/"+encodeURIComponent(id))
    .then(r=>r.json())
    .then(d=>{ bodyEl.textContent = cleanBody(d.body); })
    .catch(()=>{ bodyEl.textContent = "(본문을 불러올 수 없습니다)"; });

  document.getElementById("dp-edit-intent").value = m.intent_type || "unknown";
  document.getElementById("dp-edit-priority").value = m.personal_priority || "";
  document.getElementById("dp-edit-category").value = m.email_category || "";
  document.getElementById("dp-edit-action").value = m.suggested_action || "";
  document.getElementById("dp-save-msg").textContent = "";
  document.getElementById("ea-result").style.display = "none";
  document.getElementById("ea-result").innerHTML = "";
  const btnA = document.getElementById("btn-analyze");
  btnA.disabled = false;
  btnA.innerHTML = "&#128269; AI 오류 분석";
  document.getElementById("dp-foot").textContent = "조회 시각: "+fmtFull(new Date().toISOString());
  document.getElementById("ov").classList.add("open");
  document.getElementById("dp").classList.add("open");
}

async function saveMetaEdit(){
  if(!_selId) return;
  const btn = document.querySelector(".btn-save-meta");
  const msg = document.getElementById("dp-save-msg");
  btn.disabled = true;
  msg.style.color = "var(--tx3)";
  msg.textContent = "저장 중...";
  try{
    const payload = {
      intent_type: document.getElementById("dp-edit-intent").value || "unknown",
      personal_priority: document.getElementById("dp-edit-priority").value || null,
      email_category: document.getElementById("dp-edit-category").value || null,
      suggested_action: document.getElementById("dp-edit-action").value.trim() || null,
    };
    const res = await fetch("/dashboard/message/"+encodeURIComponent(_selId),{
      method:"PATCH",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload),
    });
    if(res.ok){
      const m = _data.find(x=>x.id===_selId);
      if(m){ Object.assign(m, payload); }
      document.getElementById("dp-sev").innerHTML = sevBadge(payload.intent_type);
      const ps = document.getElementById("dp-personal-sec");
      if(payload.personal_priority || payload.email_category){
        ps.style.display="";
        document.getElementById("dp-pp").innerHTML = ppBadge(payload.personal_priority);
        document.getElementById("dp-ec").innerHTML = ecBadge(payload.email_category);
        const af = document.getElementById("dp-action-field");
        if(payload.suggested_action){ af.style.display=""; document.getElementById("dp-suggested").textContent=payload.suggested_action; }
        else { af.style.display="none"; }
      } else { ps.style.display="none"; }
      renderTable();
      msg.style.color = "var(--c-ok)";
      msg.textContent = "✓ 저장됨";
    } else {
      msg.style.color = "var(--c-crit)";
      msg.textContent = "저장 실패";
    }
  }catch(e){
    msg.style.color = "var(--c-crit)";
    msg.textContent = "오류: "+e.message;
  } finally { btn.disabled = false; }
}

async function runErrorAnalysis(){
  if(!_selId) return;
  const btn = document.getElementById("btn-analyze");
  const res = document.getElementById("ea-result");
  btn.disabled = true;
  btn.textContent = "⏳ 분석 중...";
  res.style.display = "none";
  res.innerHTML = "";
  try{
    const r = await fetch("/dashboard/message/"+encodeURIComponent(_selId)+"/analyze");
    if(!r.ok){ throw new Error(await r.text()); }
    const d = await r.json();
    function escNl(s){ return esc(s).replace(/\\n/g,"<br>"); }
    let html = "";
    html += `<div class="ea-card">
      <div class="ea-card-title">🔴 오류 요약</div>
      <table style="font-size:12px;border-collapse:collapse;width:100%">
        <tr><td style="color:var(--tx3);font-weight:700;width:70px;padding:3px 8px 3px 0;vertical-align:top">시스템</td><td style="color:var(--tx)">${esc(d.system||"—")}</td></tr>
        <tr><td style="color:var(--tx3);font-weight:700;padding:3px 8px 3px 0;vertical-align:top">발생 시각</td><td style="color:var(--tx)">${esc(d.occurred_at||"—")}</td></tr>
        <tr><td style="color:var(--tx3);font-weight:700;padding:3px 8px 3px 0;vertical-align:top">오류</td><td style="color:var(--tx)">${esc(d.error_message||"—")}</td></tr>
        <tr><td style="color:var(--tx3);font-weight:700;padding:3px 8px 3px 0;vertical-align:top">영향 범위</td><td style="color:var(--tx)">${esc(d.impact||"—")}</td></tr>
      </table>
    </div>`;
    if(d.causes && d.causes.length){
      const causesHtml = d.causes.map(c=>{
        const lkCls = c.likelihood==="high"?"ea-lk-h":c.likelihood==="medium"?"ea-lk-m":"ea-lk-l";
        const lkTxt = c.likelihood==="high"?"HIGH":c.likelihood==="medium"?"MED":"LOW";
        return `<div class="ea-cause"><span class="ea-lk ${lkCls}">${lkTxt}</span><span style="font-size:12px;color:var(--tx)">${esc(c.desc)}</span></div>`;
      }).join("");
      html += `<div class="ea-card"><div class="ea-card-title">🔍 원인 분석</div><div>${causesHtml}</div></div>`;
    }
    html += `<div class="ea-card">
      <div class="ea-card-title">🛠️ 조치 방법</div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div><div style="font-size:10.5px;font-weight:700;color:var(--tx3);margin-bottom:4px">즉각 조치</div><div class="ea-card-body">${escNl(d.immediate_action||"—")}</div></div>
        <div style="border-top:1px solid var(--bd);padding-top:8px"><div style="font-size:10.5px;font-weight:700;color:var(--tx3);margin-bottom:4px">재발 방지</div><div class="ea-card-body">${escNl(d.prevention||"—")}</div></div>
      </div>
    </div>`;
    res.innerHTML = html;
    res.style.display = "flex";
  }catch(e){
    res.innerHTML = `<div class="ea-card"><div class="ea-card-body" style="color:var(--c-crit)">분석 실패: ${esc(String(e))}</div></div>`;
    res.style.display = "flex";
  }finally{
    btn.disabled = false;
    btn.innerHTML = "&#128269; AI 오류 분석";
  }
}

async function rowDeleteMessage(event, id){
  event.stopPropagation();
  const m = _data.find(x=>x.id===id);
  const label = m ? (m.subject||m.sender||id).slice(0,40) : id;
  if(!confirm("이 메일을 삭제하시겠습니까?\\n\\n"+label)) return;
  try{
    const r = await fetch("/dashboard/message/"+encodeURIComponent(id),{method:"DELETE"});
    if(!r.ok){ alert("삭제 실패: "+(await r.text())); return; }
    _data = _data.filter(x=>x.id!==id);
    if(_selId===id) closeDetail();
    else renderTable();
  }catch(e){ alert("오류: "+e.message); }
}

async function deleteMessage(){
  if(!_selId) return;
  const m = _data.find(x=>x.id===_selId);
  const label = m ? (m.subject||m.sender||_selId).slice(0,40) : _selId;
  if(!confirm("이 메일을 삭제하시겠습니까?\\n\\n"+label)) return;
  try{
    const r = await fetch("/dashboard/message/"+encodeURIComponent(_selId),{method:"DELETE"});
    if(!r.ok){ alert("삭제 실패: "+(await r.text())); return; }
    _data = _data.filter(x=>x.id!==_selId);
    closeDetail();
  }catch(e){ alert("오류: "+e.message); }
}

function closeDetail(){
  _selId=null; renderTable();
  document.getElementById("ov").classList.remove("open");
  document.getElementById("dp").classList.remove("open");
}

async function createJiraManually(){
  if(!_selId) return;
  const btn = document.getElementById("btn-create-jira");
  const msgEl = document.getElementById("dp-jira-msg");
  btn.disabled=true;
  msgEl.textContent="";

  if(!_jiraEnabled){
    // Jira 비활성화 → 설명 텍스트 생성 후 클립보드 복사
    btn.textContent="생성 중...";
    try{
      const res = await fetch("/dashboard/jira/preview/"+encodeURIComponent(_selId));
      const data = await res.json();
      if(res.ok){
        await navigator.clipboard.writeText(data.text);
        msgEl.style.color="var(--c-info)";
        msgEl.textContent="클립보드에 복사됐습니다.";
      } else {
        msgEl.style.color="var(--c-crit)";
        msgEl.textContent="오류: "+(data.detail||"알 수 없는 오류");
      }
    } catch(e){
      msgEl.style.color="var(--c-crit)";
      msgEl.textContent="오류: "+e.message;
    }
    btn.disabled=false;
    btn.textContent="📋 설명 복사";
    return;
  }

  // Jira 활성화 → 티켓 생성
  btn.textContent="생성 중...";
  try{
    const res = await fetch("/dashboard/jira/create/"+encodeURIComponent(_selId), {method:"POST"});
    const data = await res.json();
    if(res.ok){
      msgEl.style.color="var(--c-info)";
      msgEl.textContent="생성됨: "+data.jira_key;
      await fetchAndRender();
      const m = _data.find(x=>x.id===_selId);
      if(m) openDetail(_selId);
    } else {
      msgEl.style.color="var(--c-crit)";
      msgEl.textContent="오류: "+(data.detail||"알 수 없는 오류");
      btn.disabled=false;
      btn.textContent="&#127931; Jira 티켓 생성";
    }
  } catch(e){
    msgEl.style.color="var(--c-crit)";
    msgEl.textContent="네트워크 오류";
    btn.disabled=false;
    btn.textContent="&#127931; Jira 티켓 생성";
  }
}

document.getElementById("srch").addEventListener("input", renderTable);
document.getElementById("sev-sel").addEventListener("change", renderTable);
document.querySelectorAll(".ftab").forEach(t=>{
  t.addEventListener("click",()=>{
    document.querySelectorAll(".ftab").forEach(x=>x.classList.remove("active"));
    t.classList.add("active");
    _src = t.dataset.src;
    renderTable();
  });
});
document.getElementById("tbody").addEventListener("click", function(e){
  var a = e.target.closest("a");
  if(a) return;
  var row = e.target.closest("tr[data-id]");
  if(row) openDetail(row.dataset.id);
});

// clock + countdown
setInterval(()=>{
  document.getElementById("clock").textContent =
    new Date().toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});
  _cdwn--;
  if(_cdwn<=0) _cdwn=30;
  document.getElementById("cdwn").textContent="다음 갱신: "+_cdwn+"s";
},1000);

// 날짜 기본값 = 오늘, pg-sub는 fetchAndRender()가 설정
(function(){
  const today = new Date().toLocaleDateString("sv-SE");
  document.getElementById("ds-start").value = today;
  document.getElementById("ds-end").value   = today;
})();

fetchAndRender();
setInterval(fetchAndRender, 30000);
if(location.hash==="#report") showView("report");

// ── 날짜 검색 ──────────────────────────────────────────────
async function runDateSearch(){
  const start = document.getElementById("ds-start").value;
  const end   = document.getElementById("ds-end").value;
  if(!start || !end){ alert("시작일과 종료일을 모두 선택하세요."); return; }
  if(start > end)   { alert("시작일이 종료일보다 늦을 수 없습니다."); return; }
  await fetchAndRender();
}

function resetToToday(){
  const today = new Date().toLocaleDateString("sv-SE");
  document.getElementById("ds-start").value = today;
  document.getElementById("ds-end").value   = today;
  fetchAndRender();
}

function setDsRange(t){
  const today = new Date();
  const ts = today.toLocaleDateString("sv-SE");
  if(t==="week"){
    const mon = new Date(today);
    mon.setDate(mon.getDate() - ((mon.getDay()+6)%7));
    const sun = new Date(mon);
    sun.setDate(mon.getDate() + 6);
    document.getElementById("ds-start").value = mon.toLocaleDateString("sv-SE");
    document.getElementById("ds-end").value   = sun.toLocaleDateString("sv-SE");
  } else {
    const d = new Date(today.getFullYear(), today.getMonth(), 1);
    document.getElementById("ds-start").value = d.toLocaleDateString("sv-SE");
    document.getElementById("ds-end").value   = ts;
  }
  fetchAndRender();
}

async function openSettings(){
  try{
    const res = await fetch("/dashboard/settings");
    if(!res.ok){ alert("설정을 불러오지 못했습니다."); return; }
    const d = await res.json();
    document.getElementById("cfg-name").value = d.user_name || "";
    document.getElementById("cfg-email").value = d.user_email || "";
    document.getElementById("cfg-keywords").value = d.user_keywords || "";
    document.getElementById("cfg-jira-auto").checked = !!d.jira_auto_create;
    document.getElementById("cfg-epic-key").value = d.jira_story_epic_key || "";
    document.getElementById("cfg-sprint-name").value = d.jira_story_sprint_name || "";
    document.getElementById("cfg-account-id").value = d.jira_account_id || "";
    document.getElementById("cfg-msg").textContent = "";
    document.getElementById("cfg-msg").style.color = "";
  }catch(e){ alert("설정 로드 오류: "+e.message); return; }
  document.getElementById("settings-ov").classList.add("open");
  document.getElementById("settings-modal").classList.add("open");
}
function closeSettings(){
  document.getElementById("settings-ov").classList.remove("open");
  document.getElementById("settings-modal").classList.remove("open");
}
function _validateSettingsForm(msg){
  const emailRaw = document.getElementById("cfg-email").value.trim();
  if(emailRaw){
    const emailRe = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+[.][a-zA-Z]{2,}$/;
    const emails = emailRaw.split(",").map(e=>e.trim()).filter(Boolean);
    for(const e of emails){
      if(!emailRe.test(e)){
        msg.style.color="var(--c-crit)";
        msg.textContent="유효하지 않은 이메일 형식입니다: "+e;
        return false;
      }
    }
    if(emailRaw.length > 500){
      msg.style.color="var(--c-crit)";
      msg.textContent="이메일 주소가 너무 깁니다 (최대 500자).";
      return false;
    }
  }
  const epicKey = document.getElementById("cfg-epic-key").value.trim().toUpperCase();
  if(epicKey && !/^[A-Z][A-Z0-9]*-[0-9]+$/.test(epicKey)){
    msg.style.color="var(--c-crit)";
    msg.textContent="Epic Key 형식이 올바르지 않습니다. 예: GW-5";
    return false;
  }
  const userName = document.getElementById("cfg-name").value.trim();
  if(userName.length > 100){
    msg.style.color="var(--c-crit)";
    msg.textContent="이름은 100자를 초과할 수 없습니다.";
    return false;
  }
  const keywords = document.getElementById("cfg-keywords").value.trim();
  if(keywords.length > 500){
    msg.style.color="var(--c-crit)";
    msg.textContent="키워드는 500자를 초과할 수 없습니다.";
    return false;
  }
  return true;
}

async function saveSettings(){
  const btn = document.getElementById("cfg-save");
  const msg = document.getElementById("cfg-msg");
  msg.textContent = "";
  if(!_validateSettingsForm(msg)){ return; }
  btn.disabled = true;
  msg.style.color = "var(--tx3)";
  msg.textContent = "저장 중...";
  try{
    const res = await fetch("/dashboard/settings",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        user_name: document.getElementById("cfg-name").value.trim(),
        user_email: document.getElementById("cfg-email").value.trim(),
        user_keywords: document.getElementById("cfg-keywords").value.trim(),
        jira_auto_create: document.getElementById("cfg-jira-auto").checked,
        jira_story_epic_key: document.getElementById("cfg-epic-key").value.trim(),
        jira_story_sprint_name: document.getElementById("cfg-sprint-name").value.trim(),
        jira_account_id: document.getElementById("cfg-account-id").value.trim(),
      })
    });
    const d = await res.json();
    if(res.ok){
      _jiraAuto = document.getElementById("cfg-jira-auto").checked;
      msg.style.color = "var(--c-ok)";
      msg.textContent = "저장됐습니다. 다음 메일부터 새 설정이 적용됩니다.";
    } else {
      msg.style.color = "var(--c-crit)";
      // Pydantic v2 validation errors return detail as an array
      if(Array.isArray(d.detail)){
        msg.textContent = "입력 오류: " + d.detail.map(e=>e.msg.replace(/^Value error, /,"")).join("; ");
      } else {
        msg.textContent = "오류: "+(d.detail||"저장 실패");
      }
    }
  }catch(e){
    msg.style.color = "var(--c-crit)";
    msg.textContent = "네트워크 오류";
  }
  btn.disabled = false;
}
document.addEventListener("keydown", e=>{ if(e.key==="Escape"){ closeDetail(); closeSettings(); closeStoryModal(); } });

let _storyMsgId = null, _storyStep = 1;

async function openStoryModal(){
  if(!_selId) return;
  _storyMsgId = _selId;
  _storyStep = 1;
  document.getElementById("st-view1").classList.add("active");
  document.getElementById("st-view2").classList.remove("active");
  document.getElementById("st-analyzing").style.display="";
  document.getElementById("st-analyze-result").style.display="none";
  document.getElementById("st-field-team").style.display="none";
  document.getElementById("st-field-task").style.display="none";
  document.getElementById("btn-st-back").style.display="none";
  document.getElementById("btn-st-next").textContent="다음";
  document.getElementById("btn-st-next").disabled=true;
  document.getElementById("st-msg").textContent="";
  document.getElementById("st-labels").value="";
  document.getElementById("st-due-date").value="";
  document.getElementById("st-start-date").value="";
  const _titleEl = document.getElementById("st-preview-title-box");
  _titleEl.value=""; delete _titleEl.dataset.userEdited;
  // 우선순위 배지: intent_type → priority 매핑
  const _sm = _data.find(x=>x.id===_selId);
  const _PMAP={urgent:"Highest",task:"High",inquiry:"Medium",project:"High"};
  const _pName=_PMAP[(_sm||{}).intent_type]||"Medium";
  const _pColor=_pName==="Highest"?"var(--c-crit)":_pName==="High"?"#ffb347":"var(--acc)";
  document.getElementById("st-priority-badge").innerHTML=
    '<span style="color:'+_pColor+';font-weight:700">'+_pName+'</span>'
    +' <span style="font-size:10.5px;color:var(--tx3)">(중요도 자동 반영)</span>';
  document.getElementById("story-ov").classList.add("open");
  document.getElementById("story-modal").classList.add("open");
  try{
    const res = await fetch("/dashboard/jira/story/analyze/"+encodeURIComponent(_storyMsgId));
    const d = await res.json();
    document.getElementById("st-analyzing").style.display="none";
    const box = document.getElementById("st-analyze-box");
    box.innerHTML =
      '<div class="st-analyze-item"><span class="st-analyze-lbl">요청 팀</span><span class="st-analyze-val">'+esc(d.team||"(미확인)")+'</span></div>'+
      '<div class="st-analyze-item"><span class="st-analyze-lbl">핵심 업무</span><span class="st-analyze-val">'+esc(d.task_summary||"(미확인)")+'</span></div>'+
      '<div class="st-analyze-item"><span class="st-analyze-lbl">기한</span><span class="st-analyze-val">'+(d.deadline_str ? esc(d.deadline_str)+(d.is_overdue?" ⚠️ 초과":"") : "미정")+'</span></div>';
    document.getElementById("st-analyze-result").style.display="";
    document.getElementById("st-field-team").style.display="";
    document.getElementById("st-field-task").style.display="";
    document.getElementById("st-team").value = d.team || "";
    document.getElementById("st-task").value = d.task_summary || "";
    // LLM이 추출한 기한을 날짜 입력에 자동 채움 (예: "2026.06.30" → "2026-06-30")
    if(d.deadline_str){
      const ds = d.deadline_str.replace(/\./g,"-");
      if(/^\d{4}-\d{2}-\d{2}$/.test(ds)) document.getElementById("st-due-date").value=ds;
    }
    document.getElementById("btn-st-next").disabled=false;
  }catch(e){
    document.getElementById("st-analyzing").textContent="분석 실패: "+e.message;
    document.getElementById("btn-st-next").disabled=false;
  }
}

function closeStoryModal(){
  document.getElementById("story-ov").classList.remove("open");
  document.getElementById("story-modal").classList.remove("open");
}

function storyBack(){
  _storyStep = 1;
  document.getElementById("st-view1").classList.add("active");
  document.getElementById("st-view2").classList.remove("active");
  document.getElementById("btn-st-back").style.display="none";
  document.getElementById("btn-st-next").textContent="다음";
  document.getElementById("st-msg").textContent="";
}

function updateStoryPreview(){
  const team = (document.getElementById("st-team")||{value:""}).value.trim();
  const task = (document.getElementById("st-task")||{value:""}).value.trim();
  const md = parseFloat((document.getElementById("st-md")||{value:"1"}).value||"1") || 1;
  const el = document.getElementById("st-preview-title-box");
  // 사용자가 직접 수정한 경우 덮어쓰지 않음
  if(!el.dataset.userEdited) el.value = "["+team+"] "+task+" ("+md+" M/D)";
}

document.addEventListener("DOMContentLoaded", ()=>{
  const el = document.getElementById("st-preview-title-box");
  if(el) el.addEventListener("input", ()=>{ el.dataset.userEdited="1"; });
});

async function storyNext(){
  if(_storyStep === 1){
    const team = document.getElementById("st-team").value.trim();
    const task = document.getElementById("st-task").value.trim();
    if(!team || !task){ document.getElementById("st-msg").textContent="팀명과 업무 내용을 입력하세요."; return; }
    _storyStep = 2;
    document.getElementById("st-view1").classList.remove("active");
    document.getElementById("st-view2").classList.add("active");
    document.getElementById("btn-st-back").style.display="";
    document.getElementById("btn-st-next").textContent="Jira에 등록";
    document.getElementById("st-msg").textContent="";
    document.getElementById("st-md").addEventListener("input", updateStoryPreview);
    updateStoryPreview();
  } else {
    await submitStory();
  }
}

async function submitStory(){
  const btn = document.getElementById("btn-st-next");
  const msg = document.getElementById("st-msg");
  btn.disabled=true;
  msg.style.color="var(--tx3)";
  msg.textContent="등록 중...";
  const team      = document.getElementById("st-team").value.trim();
  const task      = document.getElementById("st-task").value.trim();
  const md        = parseFloat(document.getElementById("st-md").value||"1") || 1;
  const labels    = document.getElementById("st-labels").value.trim();
  const dueDate   = document.getElementById("st-due-date").value;
  const startDate = document.getElementById("st-start-date").value;
  try{
    const res = await fetch("/dashboard/jira/story/create/"+encodeURIComponent(_storyMsgId),{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({md, team, task_summary: task, labels, due_date: dueDate, start_date: startDate,
        story_title: document.getElementById("st-preview-title-box").value.trim()})
    });
    const d = await res.json();
    if(res.ok){
      msg.style.color="var(--c-ok)";
      msg.textContent="등록됨: "+d.jira_key;
      await fetchAndRender();
      setTimeout(closeStoryModal, 1500);
    } else {
      msg.style.color="var(--c-crit)";
      msg.textContent="오류: "+(d.detail||"등록 실패");
      btn.disabled=false;
    }
  }catch(e){
    msg.style.color="var(--c-crit)";
    msg.textContent="네트워크 오류";
    btn.disabled=false;
  }
}
// ── REPORT VIEW JS ──
let _curTab = "home";
let _charts = {};
let _mailData = [], _mailSortCol = "received_at", _mailSortDir = "desc";

function sortMailBy(col){
  if(_mailSortCol===col) _mailSortDir=_mailSortDir==="desc"?"asc":"desc";
  else{_mailSortCol=col;_mailSortDir="desc";}
  _renderMailSorted();
}

function _renderMailSorted(){
  document.querySelectorAll("#mail-thead th.sortable").forEach(th=>{
    th.classList.remove("sort-asc","sort-desc");
    if(th.dataset.col===_mailSortCol) th.classList.add(_mailSortDir==="desc"?"sort-desc":"sort-asc");
  });
  const data=[..._mailData].sort((a,b)=>{
    const av=String(a[_mailSortCol]??""), bv=String(b[_mailSortCol]??"");
    const cmp=av<bv?-1:av>bv?1:0;
    return _mailSortDir==="asc"?cmp:-cmp;
  });
  const tb=document.getElementById("mail-tbody");
  if(!data.length){tb.innerHTML=\'<tr><td colspan="4" class="empty">데이터가 없습니다</td></tr>\';return;}
  tb.innerHTML=data.map(r=>`<tr onclick="openMd(\'${esc(r.id)}\',\'${esc(r.sender)}\',\'${esc(r.subject)}\',\'${esc(r.received_at)}\',\'${esc(r.jira_key)}\')" style="cursor:pointer">
    <td class="t-time">${esc(r.received_at)}</td>
    <td>${esc(r.sender)}</td>
    <td class="t-sub" title="${esc(r.subject)}">${esc(r.subject)}</td>
    <td>${r.has_jira?\'<span class="jbadge-yes">등록완료</span>\':\'<span class="jbadge-no">미등록</span>\'}</td>
  </tr>`).join("");
}

function showView(v){
  document.getElementById("today-view").style.display = v==="today" ? "" : "none";
  document.getElementById("report-view").style.display = v==="report" ? "" : "none";
  document.getElementById("nav-today").classList.toggle("active", v==="today");
  document.getElementById("nav-report").classList.toggle("active", v==="report");
  location.hash = v==="report" ? "report" : "";
  if(v==="report") loadHome();
}

function gS(){ return document.getElementById("r-start").value; }
function gE(){ return document.getElementById("r-end").value; }

function setRange(t){
  const today = new Date();
  const ts = today.toLocaleDateString("sv-SE");
  if(t==="today"){
    document.getElementById("r-start").value = ts;
    document.getElementById("r-end").value = ts;
  } else if(t==="week"){
    const mon = new Date(today);
    mon.setDate(mon.getDate() - ((mon.getDay()+6)%7));
    const sun = new Date(mon);
    sun.setDate(mon.getDate() + 6);
    document.getElementById("r-start").value = mon.toLocaleDateString("sv-SE");
    document.getElementById("r-end").value = sun.toLocaleDateString("sv-SE");
  } else {
    const d = new Date(today.getFullYear(), today.getMonth(), 1);
    document.getElementById("r-start").value = d.toLocaleDateString("sv-SE");
    document.getElementById("r-end").value = ts;
  }
  doSearch();
}

function doSearch(){ loadRptCurrentTab(); }
function switchRptTab(tab){
  _curTab = tab;
  const keys = ["home","mail","jira","history"];
  document.querySelectorAll(".rtab").forEach((b,i)=>b.classList.toggle("active", keys[i]===tab));
  keys.forEach(k=>{ document.getElementById("tab-"+k).style.display = k===tab ? "" : "none"; });
  loadRptCurrentTab();
}

function loadRptCurrentTab(){
  if(_curTab==="home") loadHome();
  else if(_curTab==="mail") loadMail();
  else if(_curTab==="jira") loadJira();
  else loadHistory();
}

async function loadHome(){
  try{
    const s = gS(), e = gE();
    const todayStr = new Date().toLocaleDateString("sv-SE");
    const isToday = !s || (s === todayStr && e === todayStr);
    const r = await fetch("/report/summary?start="+encodeURIComponent(s)+"&end="+encodeURIComponent(e));
    const d = await r.json();
    document.getElementById("sum-mail").textContent = d.today_mail;
    document.getElementById("sum-jira").textContent = d.today_jira;
    document.getElementById("sum-rate").textContent = d.week_rate+"%";
    document.getElementById("sum-overdue").textContent = d.overdue;
    const mailLbl = document.getElementById("sum-mail-lbl");
    const jiraLbl = document.getElementById("sum-jira-lbl");
    const rateLbl = document.getElementById("sum-rate-lbl");
    if(mailLbl) mailLbl.textContent = isToday ? "오늘 수신 메일" : "기간 수신 메일";
    if(jiraLbl) jiraLbl.textContent = isToday ? "오늘 Jira 등록" : "기간 Jira 등록";
    if(rateLbl) rateLbl.textContent = isToday ? "이번 주 처리율" : "기간 처리율";
    const n = d.unprocessed||0;
    document.getElementById("unproc-txt").innerHTML = n>0
      ? "<strong style='color:var(--c-crit)'>"+n+"건</strong>의 미처리 메일(긴급/작업요청)이 Jira 등록 없이 남아 있습니다."
      : "현재 미처리 메일이 없습니다. &#10003; 모든 항목이 처리되었습니다.";
  }catch(e){ console.error(e); }
}

async function loadMail(){
  setLoading("mail-tbody", 4);
  try{
    const r = await fetch("/report/mail?start="+encodeURIComponent(gS())+"&end="+encodeURIComponent(gE()));
    const d = await r.json();
    renderMailTable(d.list||[]);
    renderBarChart("chart-team-mail","empty-team-mail", sortObj(d.by_team||{}), "rgba(43,109,255,.7)","rgba(43,109,255,.95)");
    renderLineChart("chart-monthly","empty-monthly", d.by_month||{});
  }catch(e){ console.error(e); }
}

function renderMailTable(data){
  _mailData = data;
  _renderMailSorted();
}

async function loadJira(){
  setLoading("overdue-tbody", 4);
  try{
    const r = await fetch("/report/jira?start="+encodeURIComponent(gS())+"&end="+encodeURIComponent(gE()));
    const d = await r.json();
    renderAvgCards(d.avg_days||0, d.total||0, d.by_team||{});
    renderDonut("chart-jira-status","empty-jira-status", d.by_status||{});
    renderBarChart("chart-jira-team","empty-jira-team", sortObj(d.by_team||{}), "rgba(46,202,138,.65)","rgba(46,202,138,.9)");
    renderOverdueTable(d.overdue||[]);
  }catch(e){ console.error(e); }
}

function renderAvgCards(avgDays, total, byTeam){
  const sorted = Object.entries(byTeam).sort((a,b)=>b[1]-a[1]).slice(0,3);
  let html = `
    <div class="avg-card"><div class="avg-card-lbl">전체 등록 티켓</div><div class="avg-card-val">${total}건</div><div class="avg-card-sub">조회 기간 합계</div></div>
    <div class="avg-card"><div class="avg-card-lbl">평균 처리 시간</div><div class="avg-card-val">${avgDays}일</div><div class="avg-card-sub">수신 → Jira 등록 M/D</div></div>`;
  sorted.forEach(([team,cnt])=>{
    html += `<div class="avg-card"><div class="avg-card-lbl">${esc(team)}</div><div class="avg-card-val" style="font-size:20px">${cnt}건</div><div class="avg-card-sub">요청 건수</div></div>`;
  });
  document.getElementById("avg-cards").innerHTML = html;
}

function renderOverdueTable(data){
  const tb = document.getElementById("overdue-tbody");
  if(!data.length){ tb.innerHTML='<tr><td colspan="4" class="empty">&#10003; 기한 초과 티켓이 없습니다</td></tr>'; return; }
  tb.innerHTML = data.map(r=>{
    const cls = r.overdue_days>=7?"overdue-hi":r.overdue_days>=3?"overdue-md":"overdue-lo";
    return `<tr>
      <td><a class="jlnk" href="${JIRA_BASE}${r.jira_key}" target="_blank">${esc(r.jira_key)}</a></td>
      <td class="t-sub">${esc(r.subject)}</td>
      <td class="t-time">${esc(r.due)}</td>
      <td class="${cls}">+${r.overdue_days}일</td>
    </tr>`;
  }).join("");
}

async function loadHistory(){
  setLoading("hist-tbody", 6);
  const search = document.getElementById("h-search").value.trim();
  const team = document.getElementById("h-team").value;
  const status = document.getElementById("h-status").value;
  try{
    let url = `/report/history?start=${encodeURIComponent(gS())}&end=${encodeURIComponent(gE())}`;
    if(search) url += "&search="+encodeURIComponent(search);
    if(team) url += "&team="+encodeURIComponent(team);
    if(status) url += "&status="+encodeURIComponent(status);
    const r = await fetch(url);
    const data = await r.json();
    renderHistTable(data);
    const teams = [...new Set(data.map(x=>x.team).filter(Boolean))].sort();
    const sel = document.getElementById("h-team");
    const cur = sel.value;
    sel.innerHTML = '<option value="">전체 팀</option>'+teams.map(t=>`<option value="${esc(t)}"${t===cur?" selected":""}>${esc(t)}</option>`).join("");
  }catch(e){ console.error(e); }
}

function renderHistTable(data){
  const tb = document.getElementById("hist-tbody");
  if(!data.length){ tb.innerHTML='<tr><td colspan="6" class="empty">데이터가 없습니다</td></tr>'; return; }
  tb.innerHTML = data.map(r=>`<tr>
    <td class="t-time">${esc(r.date)}</td>
    <td>${esc(r.sender)}</td>
    <td style="font-size:11px;color:var(--tx3)">${esc(r.team)}</td>
    <td class="t-sub" title="${esc(r.subject)}">${esc(r.subject)}</td>
    <td>${r.jira_key?'<a class="jlnk" href="'+JIRA_BASE+r.jira_key+'" target="_blank">'+esc(r.jira_key)+'</a>':'<span style="color:var(--tx3);font-size:11px">미등록</span>'}</td>
    <td class="t-time">${esc(r.proc_time)}</td>
  </tr>`).join("");
}

function exportCsv(){
  const p = new URLSearchParams({
    start:gS(), end:gE(),
    search: document.getElementById("h-search").value.trim(),
    team: document.getElementById("h-team").value,
    status: document.getElementById("h-status").value,
  });
  window.location.href = "/report/export.csv?"+p.toString();
}

function openMd(id, sender, subject, date, jiraKey){
  document.getElementById("md-title").textContent = subject||"메일 상세";
  document.getElementById("md-sender").textContent = sender;
  document.getElementById("md-date").textContent = date;
  document.getElementById("md-jira").innerHTML = jiraKey
    ? '<a class="jlnk" href="'+JIRA_BASE+jiraKey+'" target="_blank">'+esc(jiraKey)+'</a>'
    : "미등록";
  document.getElementById("md-body").textContent = "로딩 중...";
  document.getElementById("md-panel").classList.add("open");
  fetch("/dashboard/message/"+id).then(r=>r.json())
    .then(d=>{ document.getElementById("md-body").textContent = d.body||"(본문 없음)"; })
    .catch(()=>{ document.getElementById("md-body").textContent = "(불러올 수 없습니다)"; });
}

function closeMd(){
  document.getElementById("md-panel").classList.remove("open");
}

function mkChart(id,cfg){
  if(_charts[id]){ _charts[id].destroy(); delete _charts[id]; }
  const c = document.getElementById(id); if(!c) return;
  _charts[id] = new Chart(c, cfg);
}

function barOpts(unit){
  return {responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label(x){return " "+x.raw+unit}}}},
    scales:{x:{ticks:{color:"#7fa0c0",font:{size:10}},grid:{color:"rgba(255,255,255,.04)"}},
            y:{ticks:{color:"#7fa0c0",font:{size:10}},grid:{color:"rgba(255,255,255,.06)"},beginAtZero:true}}};
}

function renderBarChart(canvasId, emptyId, byObj, bg, border){
  const labels = Object.keys(byObj), values = Object.values(byObj);
  const empty = document.getElementById(emptyId);
  if(!labels.length){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  mkChart(canvasId,{type:"bar",data:{labels,datasets:[{data:values,backgroundColor:bg,borderColor:border,borderWidth:1,borderRadius:4}]},options:barOpts("건")});
}

function renderLineChart(canvasId, emptyId, byObj){
  const labels = Object.keys(byObj).sort(), values = labels.map(k=>byObj[k]);
  const empty = document.getElementById(emptyId);
  if(!labels.length){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  mkChart(canvasId,{type:"line",data:{labels,datasets:[{data:values,borderColor:"#2b6dff",backgroundColor:"rgba(43,109,255,.1)",fill:true,tension:0.4,pointRadius:4,pointBackgroundColor:"#2b6dff"}]},options:barOpts("건")});
}

function renderDonut(canvasId, emptyId, byObj){
  const labels=Object.keys(byObj), values=Object.values(byObj);
  const empty = document.getElementById(emptyId);
  if(!values.some(v=>v>0)){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  mkChart(canvasId,{type:"doughnut",data:{labels,datasets:[{data:values,backgroundColor:["rgba(67,90,120,.75)","rgba(43,109,255,.8)","rgba(46,202,138,.8)"],borderColor:"#0c1830",borderWidth:3}]},
    options:{responsive:true,plugins:{legend:{position:"bottom",labels:{color:"#7fa0c0",padding:14,font:{size:11}}},tooltip:{callbacks:{label(x){return " "+x.label+": "+x.raw+"건"}}}}}});
}

function sortObj(obj){ const s=Object.entries(obj).sort((a,b)=>b[1]-a[1]); return Object.fromEntries(s); }
function setLoading(tbId, cols){ document.getElementById(tbId).innerHTML='<tr><td colspan="'+cols+'" class="spinner-wrap"><div class="spin"></div></td></tr>'; }

(function(){
  const today = new Date().toLocaleDateString("sv-SE");
  const d = new Date(); d.setDate(1);
  const rStart = document.getElementById("r-start");
  const rEnd = document.getElementById("r-end");
  if(rStart) rStart.value = d.toLocaleDateString("sv-SE");
  if(rEnd) rEnd.value = today;
})();

</script>
</body>
</html>"""


class WebhookPayload(BaseModel):
    source: str                     # "outlook" | "teams"
    sender: str
    subject: str | None = None
    body: str
    received_at: datetime | None = None
    display_only: bool = False      # True = 목록 표시만, Jira 티켓 생성 안 함


class MessageMetaPatch(BaseModel):
    intent_type: str | None = None
    personal_priority: str | None = None
    email_category: str | None = None
    suggested_action: str | None = None


_EMAIL_RE = _re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_EPIC_KEY_RE = _re.compile(r"^[A-Z][A-Z0-9]*-\d+$")
_NO_NEWLINE_RE = _re.compile(r"[\r\n]")


class PersonalSettingsPayload(BaseModel):
    user_name: str = ""
    user_email: str = ""
    user_keywords: str = ""
    jira_auto_create: bool = False
    jira_story_epic_key: str = ""
    jira_story_sprint_name: str = ""
    jira_account_id: str = ""

    @field_validator("user_name")
    @classmethod
    def validate_user_name(cls, v: str) -> str:
        v = v.strip()
        if _NO_NEWLINE_RE.search(v):
            raise ValueError("이름에 줄바꿈 문자를 포함할 수 없습니다.")
        if len(v) > 100:
            raise ValueError("이름은 100자를 초과할 수 없습니다.")
        return v

    @field_validator("user_email")
    @classmethod
    def validate_user_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return v
        if _NO_NEWLINE_RE.search(v):
            raise ValueError("이메일에 줄바꿈 문자를 포함할 수 없습니다.")
        if len(v) > 500:
            raise ValueError("이메일 주소가 너무 깁니다 (최대 500자).")
        emails = [e.strip() for e in v.split(",") if e.strip()]
        for email in emails:
            if not _EMAIL_RE.match(email):
                raise ValueError(f"유효하지 않은 이메일 형식입니다: {email}")
        return ",".join(emails)

    @field_validator("user_keywords")
    @classmethod
    def validate_user_keywords(cls, v: str) -> str:
        v = v.strip()
        if _NO_NEWLINE_RE.search(v):
            raise ValueError("키워드에 줄바꿈 문자를 포함할 수 없습니다.")
        if len(v) > 500:
            raise ValueError("키워드는 500자를 초과할 수 없습니다.")
        return v

    @field_validator("jira_story_epic_key")
    @classmethod
    def validate_epic_key(cls, v: str) -> str:
        v = v.strip().upper()
        if v and not _EPIC_KEY_RE.match(v):
            raise ValueError("Epic Key 형식이 올바르지 않습니다 (예: GW-5).")
        return v

    @field_validator("jira_story_sprint_name")
    @classmethod
    def validate_sprint_name(cls, v: str) -> str:
        v = v.strip()
        if _NO_NEWLINE_RE.search(v):
            raise ValueError("스프린트 이름에 줄바꿈 문자를 포함할 수 없습니다.")
        if len(v) > 200:
            raise ValueError("스프린트 이름은 200자를 초과할 수 없습니다.")
        return v

    @field_validator("jira_account_id")
    @classmethod
    def validate_account_id(cls, v: str) -> str:
        v = v.strip()
        if _NO_NEWLINE_RE.search(v):
            raise ValueError("계정 ID에 줄바꿈 문자를 포함할 수 없습니다.")
        if len(v) > 200:
            raise ValueError("계정 ID는 200자를 초과할 수 없습니다.")
        return v


class StoryCreatePayload(BaseModel):
    md: float
    team: str = ""
    task_summary: str = ""
    labels: str = ""        # 쉼표 구분 문자열
    due_date: str = ""      # YYYY-MM-DD
    start_date: str = ""    # YYYY-MM-DD
    story_title: str = ""   # 사용자가 직접 수정한 스토리 제목


def _row_to_msg(row: dict) -> InboundMessage:
    received_at = (
        datetime.fromisoformat(row["received_at"])
        if row.get("received_at") else datetime.now(timezone.utc)
    )
    return InboundMessage(
        id=row["id"],
        source=MessageSource(row["source"]) if row.get("source") else MessageSource.OUTLOOK,
        sender=row.get("sender") or "",
        subject=row.get("subject") or "",
        body=row.get("body") or "(본문 없음)",
        received_at=received_at,
    )


def _rpt_dates(start: str, end: str) -> tuple[str, str]:
    from datetime import date as _date, timedelta, datetime as _dt
    KST = timezone(timedelta(hours=9))
    if not start:
        start = _date.today().strftime("%Y-%m-%d")
    if not end:
        end = _date.today().strftime("%Y-%m-%d")
    s = _dt.strptime(start, "%Y-%m-%d").replace(tzinfo=KST).astimezone(timezone.utc)
    e = (_dt.strptime(end, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)).astimezone(timezone.utc)
    return s.isoformat(), e.isoformat()


def _team_label(subject: str) -> str:
    m = _re.match(r"\[(.+?)\]", subject or "")
    return m.group(1) if m else "기타"


def _sender_label(sender: str) -> str:
    m = _re.match(r'^(.+?)\s*<', sender or "")
    if m:
        name = m.group(1).strip().strip('"')
        return name if name else (sender.split("@")[0] if "@" in sender else sender)
    if "@" in (sender or ""):
        return sender.split("@")[0]
    return sender or "기타"


_REPORT_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>리포트 &#8212; 마스턴투자운용</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%231a4fff'/><stop offset='1' stop-color='%230ea5e9'/></linearGradient></defs><rect width='32' height='32' rx='7' fill='url(%23g)'/><text x='16' y='22' font-family='system-ui,sans-serif' font-size='16' font-weight='900' fill='white' text-anchor='middle'>M</text></svg>">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#080f1c;--bg-s:#0b1527;--bg-e:#0e1d38;--bg-card:#0c1830;--bg-hov:#132040;--bd:rgba(255,255,255,.06);--bd2:rgba(255,255,255,.10);--bd-acc:rgba(50,120,255,.35);--tx:#dde6f4;--tx2:#7fa0c0;--tx3:#435a78;--acc:#2b6dff;--acc-dim:rgba(43,109,255,.13);--c-crit:#ff4444;--c-ok:#2eca8a;--c-med:#ffb820}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{min-height:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--tx);font-size:13px}
a{color:inherit;text-decoration:none}button{font-family:inherit;cursor:pointer}
.hdr{height:58px;background:var(--bg-s);border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;padding:0 24px;position:sticky;top:0;z-index:100}
.hdr-l{display:flex;align-items:center;gap:14px}
.back-btn{display:flex;align-items:center;justify-content:center;width:32px;height:32px;border:1px solid var(--bd2);border-radius:7px;color:var(--tx2);font-size:18px;background:transparent;transition:all .12s;flex-shrink:0}
.back-btn:hover{background:var(--bg-hov);color:var(--tx)}
.logo{width:43px;height:34px;background:linear-gradient(135deg,#1a4fff,#0ea5e9);border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:9px;color:#fff;letter-spacing:.1em;flex-shrink:0;box-shadow:0 2px 12px rgba(43,109,255,.4)}
.hdr-titles{display:flex;flex-direction:column}
.hdr-co{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.09em;text-transform:uppercase}
.hdr-sys{font-size:13.5px;font-weight:700;letter-spacing:-.02em}
.clock{font-size:12px;color:var(--tx2);font-variant-numeric:tabular-nums;font-weight:500}
.rpt-page{padding:20px 28px;max-width:1360px;margin:0 auto}
.gf-bar{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:14px;background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:11px 16px}
.gf-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.07em;text-transform:uppercase;flex-shrink:0}
.ds-date{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:6px 10px;color:var(--tx);font-size:12.5px;outline:none;font-family:inherit;transition:border-color .15s;min-width:128px}
.ds-date:focus{border-color:var(--bd-acc)}
.ds-sep{color:var(--tx3);font-size:12px}
.btn-ds-search{background:var(--acc);color:#fff;border:none;border-radius:7px;padding:6px 14px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap}
.btn{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:7px;font-size:12px;font-weight:600;border:none;transition:all .12s}
.btn-ghost{background:transparent;color:var(--tx2);border:1px solid var(--bd2)}
.btn-ghost:hover{background:var(--bg-e);color:var(--tx)}
.rtabs{display:flex;gap:2px;margin-bottom:16px;background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:4px}
.rtab{flex:1;padding:8px 10px;border:none;background:transparent;color:var(--tx2);font-size:12px;font-weight:600;border-radius:7px;cursor:pointer;transition:all .12s;white-space:nowrap}
.rtab.active{background:var(--bg-s);color:var(--tx);box-shadow:0 1px 4px rgba(0,0,0,.4)}
.rtab:hover:not(.active){color:var(--tx)}
.sum-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.sum-card{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:16px 18px;position:relative;overflow:hidden}
.sum-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2.5px;border-radius:10px 10px 0 0;background:var(--acc)}
.sum-card-warn::before{background:var(--c-crit)}
.sum-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:8px}
.sum-val{font-size:28px;font-weight:900;letter-spacing:-.04em;line-height:1;color:var(--tx)}
.sum-card-warn .sum-val{color:var(--c-crit)}
.sum-desc{font-size:10.5px;color:var(--tx3);margin-top:4px}
.unproc-banner{background:linear-gradient(135deg,rgba(255,68,68,.07),rgba(43,109,255,.07));border:1px dashed rgba(255,68,68,.25);border-radius:10px;padding:13px 18px;display:flex;align-items:center;gap:12px;cursor:pointer;transition:background .12s}
.unproc-banner:hover{background:linear-gradient(135deg,rgba(255,68,68,.12),rgba(43,109,255,.12))}
.unproc-ico{font-size:20px}
.unproc-txt{flex:1;font-size:12.5px;color:var(--tx)}
.banner-arrow{font-size:11px;color:var(--acc);font-weight:700;white-space:nowrap}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.chart-box{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:16px}
.chart-title{font-size:12px;font-weight:700;color:var(--tx2);margin-bottom:12px}
.avg-cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.avg-card{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:13px 18px;min-width:130px}
.avg-card-lbl{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px}
.avg-card-val{font-size:22px;font-weight:900;color:var(--c-ok);letter-spacing:-.03em}
.avg-card-sub{font-size:10.5px;color:var(--tx3);margin-top:3px}
.tcard{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;overflow:hidden;margin-top:14px}
.tcard-hdr{padding:11px 16px;font-size:12px;font-weight:700;color:var(--tx2);border-bottom:1px solid var(--bd)}
.twrap{overflow:auto;max-height:360px}
table{width:100%;border-collapse:collapse;min-width:480px}
thead th{padding:9px 13px;text-align:left;font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--bd);background:rgba(0,0,0,.18);white-space:nowrap;position:sticky;top:0;z-index:2}
th.sortable{cursor:pointer;user-select:none}
th.sortable:hover{color:var(--tx)}
th.sort-asc::after{content:" ▲";font-size:9px;color:var(--acc);vertical-align:middle}
th.sort-desc::after{content:" ▼";font-size:9px;color:var(--acc);vertical-align:middle}
tbody tr{border-bottom:1px solid var(--bd);transition:background .08s}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:var(--bg-hov)}
tbody td{padding:10px 13px;font-size:12px;color:var(--tx2)}
.empty{padding:44px 20px;text-align:center;color:var(--tx3);font-size:12px}
.t-sub{color:var(--tx);font-weight:500;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.t-time{font-variant-numeric:tabular-nums;white-space:nowrap;font-size:11.5px}
.jbadge-yes{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(46,202,138,.12);color:#4cd9a0}
.jbadge-no{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(255,68,68,.12);color:#ff7070}
.jlnk{color:#ffc94d;font-size:11px;font-weight:600}
.jlnk:hover{text-decoration:underline}
.overdue-hi{color:var(--c-crit);font-weight:700}
.overdue-md{color:var(--c-med);font-weight:700}
.overdue-lo{color:var(--tx2);font-weight:600}
.hist-filter{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:10px}
.srch{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:7px 10px;color:var(--tx);font-size:12px;outline:none;transition:border-color .15s;min-width:180px}
.srch:focus{border-color:var(--bd-acc)}
.srch::placeholder{color:var(--tx3)}
.fsel{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:7px 26px 7px 10px;color:var(--tx);font-size:12px;outline:none;cursor:pointer;-webkit-appearance:none;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath fill='%23435a78' d='M5 6 0 0h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 9px center}
.fsel:focus{border-color:var(--bd-acc)}
.fsel option{background:var(--bg-e)}
.modal-ov{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:200;opacity:0;pointer-events:none;transition:opacity .2s}
.modal-ov.open{opacity:1;pointer-events:all}
.md-panel{position:fixed;right:0;top:0;bottom:0;width:440px;background:#14274d;border-left:3px solid var(--acc);box-shadow:-8px 0 36px rgba(0,0,0,.7);z-index:305;transform:translateX(100%);transition:transform .22s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden}
.md-panel.open{transform:translateX(0)}
.md-hdr{padding:16px 20px;border-bottom:1px solid var(--bd2);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:10px}
.md-hdr-title{font-size:13.5px;font-weight:700;color:var(--tx);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.md-hdr button{background:rgba(255,255,255,.07);border:none;color:var(--tx2);font-size:15px;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.md-body{flex:1;overflow-y:auto;padding:18px 20px;display:flex;flex-direction:column;gap:10px}
.dp-field{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);border-radius:8px;padding:9px 11px}
.dp-field-lbl{font-size:10px;color:var(--tx3);margin-bottom:3px;font-weight:600;letter-spacing:.04em}
.dp-field-val{font-size:12px;color:var(--tx);font-weight:500;word-break:break-all}
.dp-body-text{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;font-size:11.5px;color:var(--tx2);line-height:1.65;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto}
.spinner-wrap{display:flex;justify-content:center;padding:36px}
.spin{width:26px;height:26px;border:3px solid var(--bd2);border-top-color:var(--acc);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:2px}
</style>
</head>
<body>
<header class="hdr">
  <div class="hdr-l">
    <a href="/dashboard" class="back-btn" title="대시보드로 돌아가기">&#8592;</a>
    <div class="logo">M</div>
    <div class="hdr-titles">
      <span class="hdr-co">마스턴투자운용</span>
      <span class="hdr-sys">인바운드 리포트</span>
    </div>
  </div>
  <div class="hdr-r">
    <span class="clock" id="clock">--:--:--</span>
  </div>
</header>

<div class="rpt-page">

  <!-- 공통 날짜 필터 -->
  <div class="gf-bar">
    <span class="gf-lbl">조회 기간</span>
    <input type="date" class="ds-date" id="r-start">
    <span class="ds-sep">~</span>
    <input type="date" class="ds-date" id="r-end">
    <button class="btn-ds-search" onclick="doSearch()">검색</button>
    <button class="btn btn-ghost" onclick="setRange('today')">오늘</button>
    <button class="btn btn-ghost" onclick="setRange('week')">이번 주</button>
    <button class="btn btn-ghost" onclick="setRange('month')">이번 달</button>
  </div>

  <!-- 탭 네비게이션 -->
  <div class="rtabs" id="rtabs">
    <button class="rtab active" onclick="switchTab('home')">&#127968; 대시보드</button>
    <button class="rtab" onclick="switchTab('mail')">&#128139; 메일 수신 현황</button>
    <button class="rtab" onclick="switchTab('jira')">&#127993; Jira 티켓 현황</button>
    <button class="rtab" onclick="switchTab('history')">&#128203; 처리 이력</button>
  </div>

  <!-- 탭1: 대시보드 -->
  <div class="tab-pane" id="tab-home">
    <div class="sum-cards">
      <div class="sum-card">
        <div class="sum-lbl">오늘 수신 메일</div>
        <div class="sum-val" id="sum-mail">&#8212;</div>
        <div class="sum-desc">총 수신 건수</div>
      </div>
      <div class="sum-card">
        <div class="sum-lbl">오늘 Jira 등록</div>
        <div class="sum-val" id="sum-jira">&#8212;</div>
        <div class="sum-desc">자동 생성 티켓</div>
      </div>
      <div class="sum-card">
        <div class="sum-lbl">이번 주 처리율</div>
        <div class="sum-val" id="sum-rate">&#8212;</div>
        <div class="sum-desc">메일 대비 Jira 등록률</div>
      </div>
      <div class="sum-card sum-card-warn">
        <div class="sum-lbl">&#9888; 기한 초과</div>
        <div class="sum-val" id="sum-overdue">&#8212;</div>
        <div class="sum-desc">즉시 확인 필요</div>
      </div>
    </div>
    <div class="unproc-banner" onclick="switchTab('mail')">
      <span class="unproc-ico">&#128365;</span>
      <span class="unproc-txt" id="unproc-txt">미처리 데이터 로딩 중...</span>
      <span class="banner-arrow">&#8594; 메일 수신 현황</span>
    </div>
  </div>

  <!-- 탭2: 메일 수신 현황 -->
  <div class="tab-pane" id="tab-mail" style="display:none">
    <div class="chart-row">
      <div class="chart-box">
        <div class="chart-title">팀/부서별 수신 건수</div>
        <canvas id="chart-team-mail" height="220"></canvas>
        <div id="empty-team-mail" class="empty" style="display:none">데이터가 없습니다</div>
      </div>
      <div class="chart-box">
        <div class="chart-title">월별 수신 추이</div>
        <canvas id="chart-monthly" height="220"></canvas>
        <div id="empty-monthly" class="empty" style="display:none">데이터가 없습니다</div>
      </div>
    </div>
    <div class="tcard">
      <div class="twrap">
        <table>
          <thead id="mail-thead"><tr>
            <th class="sortable sort-desc" data-col="received_at" onclick="sortMailBy('received_at')">수신일시</th>
            <th class="sortable" data-col="sender" onclick="sortMailBy('sender')">발신자</th>
            <th class="sortable" data-col="subject" onclick="sortMailBy('subject')">제목</th>
            <th class="sortable" data-col="has_jira" onclick="sortMailBy('has_jira')">Jira</th>
          </tr></thead>
          <tbody id="mail-tbody"><tr><td colspan="4" class="spinner-wrap"><div class="spin"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- 탭3: Jira 티켓 현황 -->
  <div class="tab-pane" id="tab-jira" style="display:none">
    <div class="avg-cards" id="avg-cards"></div>
    <div class="chart-row" style="margin-bottom:0">
      <div class="chart-box">
        <div class="chart-title">상태별 현황</div>
        <canvas id="chart-jira-status" height="260"></canvas>
        <div id="empty-jira-status" class="empty" style="display:none">데이터가 없습니다</div>
      </div>
      <div class="chart-box">
        <div class="chart-title">팀별 요청 건수 (내림차순)</div>
        <canvas id="chart-jira-team" height="260"></canvas>
        <div id="empty-jira-team" class="empty" style="display:none">데이터가 없습니다</div>
      </div>
    </div>
    <div class="tcard">
      <div class="tcard-hdr">&#9888;&#65039; 기한 초과 목록</div>
      <div class="twrap">
        <table>
          <thead><tr><th>티켓번호</th><th>제목</th><th>기한</th><th>초과일수</th></tr></thead>
          <tbody id="overdue-tbody"><tr><td colspan="4" class="spinner-wrap"><div class="spin"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- 탭4: 처리 이력 -->
  <div class="tab-pane" id="tab-history" style="display:none">
    <div class="hist-filter">
      <input type="text" class="srch" id="h-search" placeholder="발신자 또는 제목 검색...">
      <select class="fsel" id="h-team"><option value="">전체 팀</option></select>
      <select class="fsel" id="h-status">
        <option value="">전체 상태</option>
        <option value="jira">등록완료</option>
        <option value="no_jira">미등록</option>
      </select>
      <button class="btn-ds-search" onclick="loadHistory()">필터 적용</button>
      <button class="btn btn-ghost" style="margin-left:auto" onclick="exportCsv()">&#128190; 엑셀 다운로드</button>
    </div>
    <div class="tcard" style="margin-top:0">
      <div class="twrap">
        <table>
          <thead><tr><th>날짜</th><th>발신자</th><th>팀</th><th>제목</th><th>Jira 티켓</th><th>소요 시간</th></tr></thead>
          <tbody id="hist-tbody"><tr><td colspan="6" class="spinner-wrap"><div class="spin"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

</div><!-- /rpt-page -->

<!-- 메일 상세 패널 -->
<div class="modal-ov" id="md-ov" onclick="closeMd()"></div>
<div class="md-panel" id="md-panel">
  <div class="md-hdr">
    <span class="md-hdr-title" id="md-title">메일 상세</span>
    <button onclick="closeMd()">&#10005;</button>
  </div>
  <div class="md-body">
    <div class="dp-field"><div class="dp-field-lbl">발신자</div><div class="dp-field-val" id="md-sender"></div></div>
    <div class="dp-field"><div class="dp-field-lbl">수신일시</div><div class="dp-field-val" id="md-date"></div></div>
    <div class="dp-field"><div class="dp-field-lbl">Jira 티켓</div><div class="dp-field-val" id="md-jira">&#8212;</div></div>
    <div>
      <div style="font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.04em;margin-bottom:6px">본문</div>
      <div class="dp-body-text" id="md-body">로딩 중...</div>
    </div>
  </div>
</div>

<script>
const JIRA_BASE = "https://mastern.atlassian.net/browse/";
let _curTab = "home";
let _charts = {};
let _mailData = [], _mailSortCol = "received_at", _mailSortDir = "desc";

function sortMailBy(col){
  if(_mailSortCol===col) _mailSortDir=_mailSortDir==="desc"?"asc":"desc";
  else{_mailSortCol=col;_mailSortDir="desc";}
  _renderMailSorted();
}

function _renderMailSorted(){
  document.querySelectorAll("#mail-thead th.sortable").forEach(th=>{
    th.classList.remove("sort-asc","sort-desc");
    if(th.dataset.col===_mailSortCol) th.classList.add(_mailSortDir==="desc"?"sort-desc":"sort-asc");
  });
  const data=[..._mailData].sort((a,b)=>{
    const av=String(a[_mailSortCol]??""), bv=String(b[_mailSortCol]??"");
    const cmp=av<bv?-1:av>bv?1:0;
    return _mailSortDir==="asc"?cmp:-cmp;
  });
  const tb=document.getElementById("mail-tbody");
  if(!data.length){tb.innerHTML=\'<tr><td colspan="4" class="empty">데이터가 없습니다</td></tr>\';return;}
  tb.innerHTML=data.map(r=>`<tr onclick="openMd(\'${esc(r.id)}\',\'${esc(r.sender)}\',\'${esc(r.subject)}\',\'${esc(r.received_at)}\',\'${esc(r.jira_key)}\')" style="cursor:pointer">
    <td class="t-time">${esc(r.received_at)}</td>
    <td>${esc(r.sender)}</td>
    <td class="t-sub" title="${esc(r.subject)}">${esc(r.subject)}</td>
    <td>${r.has_jira?\'<span class="jbadge-yes">등록완료</span>\':\'<span class="jbadge-no">미등록</span>\'}</td>
  </tr>`).join("");
}

setInterval(()=>{ document.getElementById("clock").textContent = new Date().toLocaleTimeString("ko-KR"); }, 1000);

(function(){
  const today = new Date().toLocaleDateString("sv-SE");
  const d = new Date(); d.setDate(1);
  document.getElementById("r-start").value = d.toLocaleDateString("sv-SE");
  document.getElementById("r-end").value = today;
})();

function gS(){ return document.getElementById("r-start").value; }
function gE(){ return document.getElementById("r-end").value; }

function setRange(t){
  const today = new Date();
  const ts = today.toLocaleDateString("sv-SE");
  if(t==="today"){
    document.getElementById("r-start").value = ts;
    document.getElementById("r-end").value = ts;
  } else if(t==="week"){
    const d = new Date(today);
    d.setDate(d.getDate() - ((d.getDay()+6)%7));
    document.getElementById("r-start").value = d.toLocaleDateString("sv-SE");
    document.getElementById("r-end").value = ts;
  } else {
    const d = new Date(today.getFullYear(), today.getMonth(), 1);
    document.getElementById("r-start").value = d.toLocaleDateString("sv-SE");
    document.getElementById("r-end").value = ts;
  }
  doSearch();
}

function doSearch(){ loadCurrentTab(); }

function switchTab(tab){
  _curTab = tab;
  const keys = ["home","mail","jira","history"];
  document.querySelectorAll(".rtab").forEach((b,i)=>b.classList.toggle("active", keys[i]===tab));
  keys.forEach(k=>{ document.getElementById("tab-"+k).style.display = k===tab ? "" : "none"; });
  loadCurrentTab();
}

function loadCurrentTab(){
  if(_curTab==="home") loadHome();
  else if(_curTab==="mail") loadMail();
  else if(_curTab==="jira") loadJira();
  else loadHistory();
}

async function loadHome(){
  try{
    const r = await fetch("/report/summary");
    const d = await r.json();
    document.getElementById("sum-mail").textContent = d.today_mail;
    document.getElementById("sum-jira").textContent = d.today_jira;
    document.getElementById("sum-rate").textContent = d.week_rate+"%";
    document.getElementById("sum-overdue").textContent = d.overdue;
    const n = d.unprocessed||0;
    document.getElementById("unproc-txt").innerHTML = n>0
      ? "<strong style='color:var(--c-crit)'>"+n+"건</strong>의 미처리 메일(긴급/작업요청)이 Jira 등록 없이 남아 있습니다."
      : "현재 미처리 메일이 없습니다. &#10003; 모든 항목이 처리되었습니다.";
  }catch(e){ console.error(e); }
}

async function loadMail(){
  setLoading("mail-tbody", 4);
  try{
    const r = await fetch("/report/mail?start="+encodeURIComponent(gS())+"&end="+encodeURIComponent(gE()));
    const d = await r.json();
    renderMailTable(d.list||[]);
    renderBarChart("chart-team-mail","empty-team-mail", sortObj(d.by_team||{}), "rgba(43,109,255,.7)","rgba(43,109,255,.95)");
    renderLineChart("chart-monthly","empty-monthly", d.by_month||{});
  }catch(e){ console.error(e); }
}

function renderMailTable(data){
  _mailData = data;
  _renderMailSorted();
}

async function loadJira(){
  setLoading("overdue-tbody", 4);
  try{
    const r = await fetch("/report/jira?start="+encodeURIComponent(gS())+"&end="+encodeURIComponent(gE()));
    const d = await r.json();
    renderAvgCards(d.avg_days||0, d.total||0, d.by_team||{});
    renderDonut("chart-jira-status","empty-jira-status", d.by_status||{});
    renderBarChart("chart-jira-team","empty-jira-team", sortObj(d.by_team||{}), "rgba(46,202,138,.65)","rgba(46,202,138,.9)");
    renderOverdueTable(d.overdue||[]);
  }catch(e){ console.error(e); }
}

function renderAvgCards(avgDays, total, byTeam){
  const sorted = Object.entries(byTeam).sort((a,b)=>b[1]-a[1]).slice(0,3);
  let html = `
    <div class="avg-card"><div class="avg-card-lbl">전체 등록 티켓</div><div class="avg-card-val">${total}건</div><div class="avg-card-sub">조회 기간 합계</div></div>
    <div class="avg-card"><div class="avg-card-lbl">평균 처리 시간</div><div class="avg-card-val">${avgDays}일</div><div class="avg-card-sub">수신 → Jira 등록 M/D</div></div>`;
  sorted.forEach(([team,cnt])=>{
    html += `<div class="avg-card"><div class="avg-card-lbl">${esc(team)}</div><div class="avg-card-val" style="font-size:20px">${cnt}건</div><div class="avg-card-sub">요청 건수</div></div>`;
  });
  document.getElementById("avg-cards").innerHTML = html;
}

function renderOverdueTable(data){
  const tb = document.getElementById("overdue-tbody");
  if(!data.length){ tb.innerHTML='<tr><td colspan="4" class="empty">&#10003; 기한 초과 티켓이 없습니다</td></tr>'; return; }
  tb.innerHTML = data.map(r=>{
    const cls = r.overdue_days>=7?"overdue-hi":r.overdue_days>=3?"overdue-md":"overdue-lo";
    return `<tr>
      <td><a class="jlnk" href="${JIRA_BASE}${r.jira_key}" target="_blank">${esc(r.jira_key)}</a></td>
      <td class="t-sub">${esc(r.subject)}</td>
      <td class="t-time">${esc(r.due)}</td>
      <td class="${cls}">+${r.overdue_days}일</td>
    </tr>`;
  }).join("");
}

async function loadHistory(){
  setLoading("hist-tbody", 6);
  const search = document.getElementById("h-search").value.trim();
  const team = document.getElementById("h-team").value;
  const status = document.getElementById("h-status").value;
  try{
    let url = `/report/history?start=${encodeURIComponent(gS())}&end=${encodeURIComponent(gE())}`;
    if(search) url += "&search="+encodeURIComponent(search);
    if(team) url += "&team="+encodeURIComponent(team);
    if(status) url += "&status="+encodeURIComponent(status);
    const r = await fetch(url);
    const data = await r.json();
    renderHistTable(data);
    // populate team dropdown
    const teams = [...new Set(data.map(x=>x.team).filter(Boolean))].sort();
    const sel = document.getElementById("h-team");
    const cur = sel.value;
    sel.innerHTML = '<option value="">전체 팀</option>'+teams.map(t=>`<option value="${esc(t)}"${t===cur?" selected":""}>${esc(t)}</option>`).join("");
  }catch(e){ console.error(e); }
}

function renderHistTable(data){
  const tb = document.getElementById("hist-tbody");
  if(!data.length){ tb.innerHTML='<tr><td colspan="6" class="empty">데이터가 없습니다</td></tr>'; return; }
  tb.innerHTML = data.map(r=>`<tr>
    <td class="t-time">${esc(r.date)}</td>
    <td>${esc(r.sender)}</td>
    <td style="font-size:11px;color:var(--tx3)">${esc(r.team)}</td>
    <td class="t-sub" title="${esc(r.subject)}">${esc(r.subject)}</td>
    <td>${r.jira_key?'<a class="jlnk" href="'+JIRA_BASE+r.jira_key+'" target="_blank">'+esc(r.jira_key)+'</a>':'<span style="color:var(--tx3);font-size:11px">미등록</span>'}</td>
    <td class="t-time">${esc(r.proc_time)}</td>
  </tr>`).join("");
}

function exportCsv(){
  const p = new URLSearchParams({
    start:gS(), end:gE(),
    search: document.getElementById("h-search").value.trim(),
    team: document.getElementById("h-team").value,
    status: document.getElementById("h-status").value,
  });
  window.location.href = "/report/export.csv?"+p.toString();
}

function openMd(id, sender, subject, date, jiraKey){
  document.getElementById("md-title").textContent = subject||"메일 상세";
  document.getElementById("md-sender").textContent = sender;
  document.getElementById("md-date").textContent = date;
  document.getElementById("md-jira").innerHTML = jiraKey
    ? '<a class="jlnk" href="'+JIRA_BASE+jiraKey+'" target="_blank">'+esc(jiraKey)+'</a>'
    : "미등록";
  document.getElementById("md-body").textContent = "로딩 중...";
  document.getElementById("md-panel").classList.add("open");
  fetch("/dashboard/message/"+id).then(r=>r.json())
    .then(d=>{ document.getElementById("md-body").textContent = d.body||"(본문 없음)"; })
    .catch(()=>{ document.getElementById("md-body").textContent = "(불러올 수 없습니다)"; });
}

function closeMd(){
  document.getElementById("md-panel").classList.remove("open");
}

function mkChart(id,cfg){
  if(_charts[id]){ _charts[id].destroy(); delete _charts[id]; }
  const c = document.getElementById(id); if(!c) return;
  _charts[id] = new Chart(c, cfg);
}

function barOpts(unit){
  return {responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label(x){return " "+x.raw+unit}}}},
    scales:{x:{ticks:{color:"#7fa0c0",font:{size:10}},grid:{color:"rgba(255,255,255,.04)"}},
            y:{ticks:{color:"#7fa0c0",font:{size:10}},grid:{color:"rgba(255,255,255,.06)"},beginAtZero:true}}};
}

function renderBarChart(canvasId, emptyId, byObj, bg, border){
  const labels = Object.keys(byObj), values = Object.values(byObj);
  const empty = document.getElementById(emptyId);
  if(!labels.length){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  mkChart(canvasId,{type:"bar",data:{labels,datasets:[{data:values,backgroundColor:bg,borderColor:border,borderWidth:1,borderRadius:4}]},options:barOpts("건")});
}

function renderLineChart(canvasId, emptyId, byObj){
  const labels = Object.keys(byObj).sort(), values = labels.map(k=>byObj[k]);
  const empty = document.getElementById(emptyId);
  if(!labels.length){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  mkChart(canvasId,{type:"line",data:{labels,datasets:[{data:values,borderColor:"#2b6dff",backgroundColor:"rgba(43,109,255,.1)",fill:true,tension:0.4,pointRadius:4,pointBackgroundColor:"#2b6dff"}]},options:barOpts("건")});
}

function renderDonut(canvasId, emptyId, byObj){
  const labels=Object.keys(byObj), values=Object.values(byObj);
  const empty = document.getElementById(emptyId);
  if(!values.some(v=>v>0)){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  mkChart(canvasId,{type:"doughnut",data:{labels,datasets:[{data:values,backgroundColor:["rgba(67,90,120,.75)","rgba(43,109,255,.8)","rgba(46,202,138,.8)"],borderColor:"#0c1830",borderWidth:3}]},
    options:{responsive:true,plugins:{legend:{position:"bottom",labels:{color:"#7fa0c0",padding:14,font:{size:11}}},tooltip:{callbacks:{label(x){return " "+x.label+": "+x.raw+"건"}}}}}});
}

function sortObj(obj){ const s=Object.entries(obj).sort((a,b)=>b[1]-a[1]); return Object.fromEntries(s); }
function setLoading(tbId, cols){ document.getElementById(tbId).innerHTML='<tr><td colspan="'+cols+'" class="spinner-wrap"><div class="spin"></div></td></tr>'; }
function esc(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

loadHome();
</script>
</body>
</html>"""


def create_app(pipeline: "Pipeline") -> FastAPI:
    app = FastAPI(title="Inbound GW Agent", docs_url=None, redoc_url=None)
    settings = get_settings()

    @app.middleware("http")
    async def _dashboard_auth_middleware(request: Request, call_next):
        """대시보드·리포트 접근 시 HTTP Basic Auth 검증 (DASHBOARD_SECRET 설정 시 활성화)."""
        path = request.url.path
        if settings.dashboard_secret and (
            path.startswith("/dashboard") or path.startswith("/report")
        ):
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Basic "):
                try:
                    decoded = _base64.b64decode(auth[6:]).decode("utf-8")
                    password = decoded.split(":", 1)[1] if ":" in decoded else ""
                    if hmac.compare_digest(
                        password.encode("utf-8"),
                        settings.dashboard_secret.encode("utf-8"),
                    ):
                        return await call_next(request)
                except Exception:
                    pass
            from fastapi.responses import Response as _Resp
            return _Resp(
                content="Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Dashboard"'},
            )
        return await call_next(request)

    @app.get("/")
    async def root():
        return {"status": "ok", "endpoints": {"webhook": "POST /webhook/message", "health": "GET /health", "dashboard": "GET /dashboard"}}

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        return _DASHBOARD_HTML

    @app.get("/dashboard/data")
    async def dashboard_data():
        return pipeline._store.get_today_messages()

    @app.get("/dashboard/search")
    async def search_messages(start: str, end: str):
        try:
            return pipeline._store.get_messages_by_date_range(start, end)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"날짜 형식 오류: {exc}") from exc

    @app.get("/dashboard/config")
    async def dashboard_config():
        s = get_settings()
        return {"jira_enabled": s.jira_enabled, "jira_auto_create": s.jira_auto_create, "user_name": s.user_name or ""}

    @app.get("/dashboard/settings")
    async def get_personal_settings():
        s = get_settings()
        return {
            "user_name": s.user_name or "",
            "user_email": s.user_email or "",
            "user_keywords": s.user_keywords or "",
            "jira_auto_create": s.jira_auto_create,
            "jira_story_epic_key": s.jira_story_epic_key or "",
            "jira_story_sprint_name": s.jira_story_sprint_name or "",
            "jira_account_id": s.jira_account_id or "",
        }

    @app.post("/dashboard/settings")
    async def update_personal_settings(payload: PersonalSettingsPayload):
        env_path = Path(".env")
        updates = {
            "USER_NAME": payload.user_name,
            "USER_EMAIL": payload.user_email,
            "USER_KEYWORDS": payload.user_keywords,
            "JIRA_AUTO_CREATE": "true" if payload.jira_auto_create else "false",
            "JIRA_STORY_EPIC_KEY": payload.jira_story_epic_key,
            "JIRA_STORY_SPRINT_NAME": payload.jira_story_sprint_name,
            "JIRA_ACCOUNT_ID": payload.jira_account_id,
        }
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        updated_keys: set[str] = set()
        new_lines: list[str] = []
        for line in lines:
            key = line.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        for key, val in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={val}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        get_settings.cache_clear()
        pipeline.reload_llm()
        log.info("personal_settings_updated", user_name=payload.user_name, user_email=payload.user_email[:20] if payload.user_email else "")
        return {"status": "ok"}

    @app.get("/dashboard/message/{message_id}")
    async def get_message_body(message_id: str):
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        return {"body": row.get("body") or ""}

    @app.patch("/dashboard/message/{message_id}")
    async def patch_message_meta(message_id: str, payload: MessageMetaPatch):
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        pipeline._store._conn.execute(
            "UPDATE processed_messages SET intent_type=?, personal_priority=?, email_category=?, suggested_action=? WHERE id=?",
            (payload.intent_type, payload.personal_priority, payload.email_category, payload.suggested_action, message_id),
        )
        pipeline._store._conn.commit()
        return {"status": "ok"}

    @app.get("/dashboard/message/{message_id}/analyze")
    async def analyze_message_error(message_id: str):
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        from inbound_gw_agent.models.message import InboundMessage, MessageSource
        msg = InboundMessage(
            id=row["id"],
            source=MessageSource(row["source"]),
            sender=row["sender"],
            subject=row.get("subject"),
            body=row["body"],
            received_at=row.get("received_at"),
        )
        handler = pipeline._handler
        if handler is None:
            from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
            handler = JiraTicketHandler()
        result = await handler.analyze_error(msg)
        return result

    @app.delete("/dashboard/message/{message_id}")
    async def delete_message(message_id: str):
        deleted = pipeline._store.delete_message(message_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        return {"status": "ok"}

    @app.get("/dashboard/jira/preview/{message_id}")
    async def preview_jira_description(message_id: str):
        """Jira 생성 없이 티켓 설명 텍스트만 생성 (JIRA_ENABLED=false 용)."""
        import ollama as _ollama
        from inbound_gw_agent.handlers.ticket_handler import (
            _SUMMARIZE_SYSTEM, _extract_sender_name,
        )
        from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType

        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")

        received_at = (
            datetime.fromisoformat(row["received_at"])
            if row.get("received_at") else datetime.now(timezone.utc)
        )
        msg = InboundMessage(
            id=row["id"],
            source=MessageSource(row["source"]) if row.get("source") else MessageSource.OUTLOOK,
            sender=row.get("sender") or "",
            subject=row.get("subject") or "",
            body=row.get("body") or "(본문 없음)",
            received_at=received_at,
        )

        ollama_client = _ollama.AsyncClient(host=settings.ollama_base_url)
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"본문:\n{msg.body[:2000]}"
        )
        try:
            response = await ollama_client.chat(
                model=settings.ollama_model,
                messages=[
                    {"role": "system", "content": _SUMMARIZE_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
            )
            content_summary = response.message.content.strip()
        except Exception as exc:
            log.warning("jira_preview_summarize_failed", error=str(exc)[:120])
            content_summary = msg.subject or msg.body[:200]

        sender_name = _extract_sender_name(msg.sender)
        text = (
            f"요청자 : {sender_name}\n\n"
            f"내용 :\n{content_summary}\n\n"
            f"메일 내용 캡처 :\n{msg.body}"
        )
        return {"text": text}

    @app.post("/dashboard/jira/create/{message_id}")
    async def create_jira_manually(message_id: str):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType

        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        if row.get("jira_key"):
            raise HTTPException(status_code=409, detail=f"이미 Jira 티켓이 존재합니다: {row['jira_key']}")
        if not settings.jira_enabled:
            raise HTTPException(status_code=400, detail="Jira가 비활성화 상태입니다. .env에서 JIRA_ENABLED=true로 설정하세요.")

        msg = _row_to_msg(row)
        intent_val = row.get("intent_type") or "unknown"
        try:
            intent_type = IntentType(intent_val)
        except ValueError:
            intent_type = IntentType.UNKNOWN
        intent = ClassifiedIntent(type=intent_type, confidence=1.0, classifier="manual")

        try:
            handler = JiraTicketHandler()
            jira_key = await handler.handle(msg, intent)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Jira 연결 오류: {exc}") from exc

        if not jira_key:
            raise HTTPException(status_code=500, detail="Jira 티켓 생성에 실패했습니다.")

        pipeline._store.update_jira_key(message_id, jira_key)
        log.info("jira_created_manually", message_id=message_id[:8], jira_key=jira_key)
        return {"status": "created", "jira_key": jira_key}

    @app.get("/dashboard/jira/story/analyze/{message_id}")
    async def analyze_for_story(message_id: str):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler

        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        msg = _row_to_msg(row)
        handler = JiraTicketHandler()
        return await handler.analyze_for_story(msg)

    _STORY_PRIORITY_MAP = {
        "urgent": "Highest", "task": "High",
        "inquiry": "Medium", "project": "High",
    }

    @app.post("/dashboard/jira/story/create/{message_id}")
    async def create_story(message_id: str, payload: StoryCreatePayload):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler

        if not settings.jira_enabled:
            raise HTTPException(status_code=400, detail="Jira가 비활성화 상태입니다. .env에서 JIRA_ENABLED=true로 설정하세요.")
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        msg = _row_to_msg(row)
        priority = _STORY_PRIORITY_MAP.get(row.get("intent_type") or "", "Medium")
        user_labels = [l.strip() for l in payload.labels.split(",") if l.strip()]
        custom_title = payload.story_title.strip() or None
        try:
            handler = JiraTicketHandler()
            jira_key = await handler.create_story(
                msg, payload.md, payload.team, payload.task_summary,
                labels=user_labels,
                due_date=payload.due_date or None,
                custom_title=custom_title,
                start_date=payload.start_date or None,
                priority=priority,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Jira 연결 오류: {exc}") from exc
        if not jira_key:
            raise HTTPException(status_code=500, detail="Jira 스토리 생성에 실패했습니다.")
        pipeline._store.update_jira_key(message_id, jira_key)
        log.info("jira_story_created_manually", message_id=message_id[:8], jira_key=jira_key)
        return {"status": "created", "jira_key": jira_key}

    # ── REPORT ENDPOINTS ──────────────────────────────────────────────

    @app.get("/report", response_class=HTMLResponse)
    async def report_page():
        return _REPORT_HTML

    @app.get("/report/summary")
    async def report_summary(start: str = "", end: str = ""):
        s_iso, e_iso = _rpt_dates(start, end)
        period_rows = pipeline._store._conn.execute(
            "SELECT jira_key FROM processed_messages"
            " WHERE COALESCE(received_at,processed_at) >= ? AND COALESCE(received_at,processed_at) < ?",
            (s_iso, e_iso),
        ).fetchall()
        period_total = len(period_rows)
        period_jira = sum(1 for r in period_rows if r[0])
        period_rate = round(period_jira / period_total * 100) if period_total else 0
        unprocessed = pipeline._store._conn.execute(
            "SELECT COUNT(*) FROM processed_messages"
            " WHERE jira_key IS NULL AND intent_type IN ('urgent','task')"
            " AND COALESCE(received_at,processed_at) >= ? AND COALESCE(received_at,processed_at) < ?",
            (s_iso, e_iso),
        ).fetchone()[0]
        return {
            "today_mail": period_total,
            "today_jira": period_jira,
            "week_rate": period_rate,
            "overdue": 0,
            "unprocessed": unprocessed,
        }

    @app.get("/report/mail")
    async def report_mail(start: str = "", end: str = ""):
        from datetime import timedelta, datetime as _dt
        KST = timezone(timedelta(hours=9))
        s_iso, e_iso = _rpt_dates(start, end)
        rows = pipeline._store._conn.execute(
            "SELECT id, sender, subject, jira_key,"
            " COALESCE(received_at,processed_at) AS received_at"
            " FROM processed_messages"
            " WHERE COALESCE(received_at,processed_at) >= ? AND COALESCE(received_at,processed_at) < ?"
            " ORDER BY COALESCE(received_at,processed_at) DESC",
            (s_iso, e_iso),
        ).fetchall()
        mail_list, by_team, by_month = [], {}, {}
        for id_, sender, subject, jira_key, received_at in rows:
            team = _team_label(subject)
            try:
                dt = _dt.fromisoformat(received_at).astimezone(KST)
                dt_disp = dt.strftime("%Y-%m-%d %H:%M")
                month_key = dt.strftime("%Y-%m")
            except Exception:
                dt_disp, month_key = received_at or "", "기타"
            mail_list.append({
                "id": id_, "received_at": dt_disp,
                "sender": _sender_label(sender or ""),
                "subject": subject or "", "team": team,
                "has_jira": bool(jira_key), "jira_key": jira_key or "",
            })
            by_team[team] = by_team.get(team, 0) + 1
            by_month[month_key] = by_month.get(month_key, 0) + 1
        return {"list": mail_list, "by_team": by_team, "by_month": by_month}

    @app.get("/report/jira")
    async def report_jira(start: str = "", end: str = ""):
        import asyncio
        from datetime import date as _date, timedelta, datetime as _dt
        KST = timezone(timedelta(hours=9))
        s_iso, e_iso = _rpt_dates(start, end)
        rows = pipeline._store._conn.execute(
            "SELECT id, sender, subject, jira_key, received_at, processed_at"
            " FROM processed_messages"
            " WHERE jira_key IS NOT NULL"
            " AND COALESCE(received_at,processed_at) >= ? AND COALESCE(received_at,processed_at) < ?"
            " ORDER BY COALESCE(received_at,processed_at) DESC",
            (s_iso, e_iso),
        ).fetchall()
        tickets, by_team = [], {}
        total_days, n_days = 0.0, 0
        for id_, sender, subject, jira_key, received_at, processed_at in rows:
            team = _team_label(subject)
            proc_min = None
            try:
                ra = _dt.fromisoformat(received_at or processed_at)
                pa = _dt.fromisoformat(processed_at)
                diff_min = (pa - ra).total_seconds() / 60
                proc_min = round(diff_min)
                total_days += diff_min / 480
                n_days += 1
            except Exception:
                pass
            tickets.append({
                "id": id_, "jira_key": jira_key, "subject": subject or "",
                "sender": _sender_label(sender or ""), "team": team, "proc_minutes": proc_min,
            })
            by_team[team] = by_team.get(team, 0) + 1
        avg_days = round(total_days / n_days, 1) if n_days else 0
        by_status: dict = {"해야 할 일": 0, "진행 중": 0, "완료": 0}
        overdue_list: list = []
        if settings.jira_enabled and settings.jira_server and tickets:
            try:
                from jira import JIRA
                jira_keys = [t["jira_key"] for t in tickets][:50]
                def _fetch_statuses():
                    jira = JIRA(
                        server=settings.jira_server,
                        basic_auth=(settings.jira_email, settings.jira_api_token),
                    )
                    issues = jira.search_issues(
                        "key in (" + ",".join(jira_keys) + ")",
                        fields="status,summary,duedate", maxResults=50,
                    )
                    return {i.key: {"status": i.fields.status.name,
                                    "due": getattr(i.fields, "duedate", None),
                                    "summary": i.fields.summary} for i in issues}
                jira_data = await asyncio.to_thread(_fetch_statuses)
                _smap = {
                    "To Do": "해야 할 일", "해야 할 일": "해야 할 일",
                    "In Progress": "진행 중", "진행 중": "진행 중",
                    "Done": "완료", "완료": "완료",
                }
                today_d = _date.today()
                for t in tickets:
                    info = jira_data.get(t["jira_key"])
                    st = _smap.get(info["status"], "해야 할 일") if info else "해야 할 일"
                    by_status[st] = by_status.get(st, 0) + 1
                    if info and info.get("due"):
                        try:
                            due = _date.fromisoformat(info["due"])
                            if due < today_d:
                                overdue_list.append({
                                    "jira_key": t["jira_key"],
                                    "subject": info.get("summary") or t["subject"],
                                    "due": info["due"],
                                    "overdue_days": (today_d - due).days,
                                })
                        except Exception:
                            pass
            except Exception as exc:
                log.warning("jira_report_fetch_failed", error=str(exc)[:120])
                by_status = {"해야 할 일": len(tickets), "진행 중": 0, "완료": 0}
        else:
            by_status = {"해야 할 일": len(tickets), "진행 중": 0, "완료": 0}
        return {
            "tickets": tickets, "by_status": by_status, "by_team": by_team,
            "overdue": overdue_list, "avg_days": avg_days, "total": len(tickets),
        }

    @app.get("/report/history")
    async def report_history(start: str = "", end: str = "", search: str = "", team: str = "", status: str = ""):
        from datetime import timedelta, datetime as _dt
        KST = timezone(timedelta(hours=9))
        s_iso, e_iso = _rpt_dates(start, end)
        rows = pipeline._store._conn.execute(
            "SELECT id, sender, subject, intent_type, jira_key,"
            " COALESCE(received_at,processed_at) AS received_at, processed_at"
            " FROM processed_messages"
            " WHERE COALESCE(received_at,processed_at) >= ? AND COALESCE(received_at,processed_at) < ?"
            " ORDER BY COALESCE(received_at,processed_at) DESC",
            (s_iso, e_iso),
        ).fetchall()
        result = []
        for id_, sender, subject, intent_type, jira_key, received_at, processed_at in rows:
            t = _team_label(subject)
            sl = _sender_label(sender or "")
            if search and not any(search.lower() in str(v or "").lower() for v in [sl, subject, t]):
                continue
            if team and t != team:
                continue
            if status == "jira" and not jira_key:
                continue
            if status == "no_jira" and jira_key:
                continue
            proc_str = "-"
            try:
                ra = _dt.fromisoformat(received_at or processed_at)
                pa = _dt.fromisoformat(processed_at)
                m = int((pa - ra).total_seconds() / 60)
                if m < 60:
                    proc_str = f"{m}분"
                elif m < 1440:
                    proc_str = f"{m // 60}시간 {m % 60}분"
                else:
                    proc_str = f"{m // 1440}일"
            except Exception:
                pass
            try:
                dt_disp = _dt.fromisoformat(received_at or processed_at).astimezone(KST).strftime("%Y-%m-%d %H:%M")
            except Exception:
                dt_disp = received_at or ""
            result.append({
                "id": id_, "date": dt_disp, "sender": sl, "subject": subject or "",
                "team": t, "jira_key": jira_key or "", "proc_time": proc_str,
                "intent_type": intent_type or "",
            })
        return result

    @app.get("/report/export.csv")
    async def export_report_csv(start: str = "", end: str = "", search: str = "", team: str = "", status: str = ""):
        from fastapi.responses import StreamingResponse
        data = await report_history(start=start, end=end, search=search, team=team, status=status)
        out = _io.StringIO()
        w = _csv.writer(out)
        w.writerow(["날짜", "발신자", "팀", "제목", "Jira 티켓", "분류", "소요 시간"])
        for r in data:
            w.writerow([r["date"], r["sender"], r["team"], r["subject"],
                        r["jira_key"], r["intent_type"], r["proc_time"]])
        content = out.getvalue().encode("utf-8-sig")
        return StreamingResponse(
            iter([content]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": "attachment; filename=inbound_report.csv"},
        )

    # ──────────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/webhook/message")
    async def receive_message(
        request: Request,
        payload: WebhookPayload,
        x_webhook_secret: str | None = Header(default=None),
    ):
        # 시크릿 검증 (WEBHOOK_SECRET 설정 시 활성화)
        # hmac.compare_digest: 타이밍 공격 방어 — 문자열 길이에 무관하게 일정한 시간 비교
        if settings.webhook_secret:
            if x_webhook_secret is None or not hmac.compare_digest(
                x_webhook_secret.encode(),
                settings.webhook_secret.encode(),
            ):
                raise HTTPException(status_code=403, detail="Invalid secret")

        try:
            source = MessageSource(payload.source.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown source: {payload.source}")

        received_at = payload.received_at or datetime.now(timezone.utc)
        # 중복 방지용 ID: 발신자 + 수신시각 + 본문 앞 50자 해시
        raw_id = f"{payload.sender}|{received_at.isoformat()}|{payload.body[:50]}"
        msg_id = hashlib.sha256(raw_id.encode()).hexdigest()[:32]

        msg = InboundMessage(
            id=msg_id,
            source=source,
            sender=payload.sender,
            subject=payload.subject,
            body=payload.body,
            received_at=received_at,
        )

        log.info("webhook_received", source=source.value, sender=payload.sender, id=msg_id[:8], display_only=payload.display_only)

        if payload.display_only:
            if not pipeline._store.is_processed(msg_id):
                pipeline._store.mark_processed(
                    message_id=msg_id,
                    source=source.value,
                    sender=payload.sender,
                    subject=payload.subject,
                    received_at=received_at.isoformat(),
                )
            return {"status": "stored", "id": msg_id[:8]}

        await pipeline.process_message(msg)
        return {"status": "accepted", "id": msg_id[:8]}

    return app
