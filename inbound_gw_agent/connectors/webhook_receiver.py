from __future__ import annotations

import base64 as _base64
import csv as _csv
import hmac
import io as _io
import re as _re
import uuid as _uuid
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
from inbound_gw_agent.utils.message_id import generate_message_id

if TYPE_CHECKING:
    from inbound_gw_agent.pipeline import Pipeline

log = structlog.get_logger()

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>마스턴투자운용 — 오류 자동수정 시스템</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%237c6de8'/><stop offset='1' stop-color='%23a78bfa'/></linearGradient></defs><rect width='32' height='32' rx='7' fill='url(%23g)'/><text x='16' y='22' font-family='system-ui,sans-serif' font-size='16' font-weight='900' fill='white' text-anchor='middle'>M</text></svg>">
<style>
:root {
  --bg:       #faf8ff;
  --bg-s:     #f3f0fd;
  --bg-e:     #ede8fb;
  --bg-card:  #f6f3fe;
  --bg-hov:   #e6e0f8;
  --bd:       rgba(140,118,200,.14);
  --bd2:      rgba(140,118,200,.26);
  --bd-acc:   rgba(110,85,220,.40);
  --tx:       #2c2450;
  --tx2:      #6a5d8a;
  --tx3:      #a898c4;
  --acc:      #7c6de8;
  --acc-dim:  rgba(124,109,232,.12);
  --c-crit:   #d04060;
  --c-high:   #c06840;
  --c-med:    #a07828;
  --c-low:    #4068c8;
  --c-info:   #208878;
  --c-ok:     #388068;
  --c-fix:    #8050b8;
  --c-spam:   #80709a;
}
html[data-theme="dark"]{
  --bg:#080f1c;--bg-s:#0b1527;--bg-e:#0e1d38;--bg-card:#0c1830;--bg-hov:#132040;
  --bd:rgba(255,255,255,.06);--bd2:rgba(255,255,255,.10);--bd-acc:rgba(50,120,255,.35);
  --tx:#dde6f4;--tx2:#7fa0c0;--tx3:#435a78;--acc:#2b6dff;--acc-dim:rgba(43,109,255,.13);
  --c-crit:#ff4444;--c-high:#ff7a29;--c-med:#ffb820;--c-low:#4a90ff;--c-info:#38d9c4;--c-ok:#2eca8a;--c-fix:#a855f7;--c-spam:#6a8299;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--tx);font-size:13px;overflow:hidden}
a{color:inherit;text-decoration:none}
button{font-family:inherit;cursor:pointer}

/* ── HEADER ── */
.hdr{height:58px;background:var(--bg-s);border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;padding:0 24px 0 0;position:relative;z-index:10;flex-shrink:0}
.hdr-l{display:flex;align-items:center;gap:14px;width:255px;flex-shrink:0;padding-left:16px;overflow:hidden;border-right:1px solid var(--bd);transition:width .22s cubic-bezier(.4,0,.2,1),padding .22s,gap .22s}
.logo{width:43px;height:34px;background:linear-gradient(135deg,#7c6de8,#a78bfa);border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:9px;color:#fff;letter-spacing:.1em;flex-shrink:0;box-shadow:0 2px 12px rgba(124,109,232,.35);overflow:hidden;max-width:43px;transition:max-width .22s cubic-bezier(.4,0,.2,1),opacity .18s}
.hdr-titles{display:flex;flex-direction:column;overflow:hidden;max-width:240px;transition:max-width .22s cubic-bezier(.4,0,.2,1),opacity .18s}
.hdr-co{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.09em;text-transform:uppercase;white-space:nowrap}
.hdr-sys{font-size:13.5px;font-weight:700;letter-spacing:-.02em;white-space:nowrap}
.live{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:700;color:var(--c-ok);letter-spacing:.05em}
.hdr.sb-collapsed .hdr-l{width:56px;padding-left:0;justify-content:center;gap:0}
.hdr.sb-collapsed .logo{max-width:0;opacity:0}
.hdr.sb-collapsed .hdr-titles{max-width:0;opacity:0}
#hdr-sb-btn{flex-shrink:0}
.hdr.sb-collapsed #hdr-sb-btn{margin-left:0}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--c-ok);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.hdr-r{display:flex;align-items:center;gap:16px}
.clock{font-size:12px;color:var(--tx2);font-variant-numeric:tabular-nums;font-weight:500;letter-spacing:.02em}
.last-upd{font-size:11px;color:var(--tx3)}

/* ── LAYOUT ── */
.wrap{display:flex;height:calc(100vh - 58px)}

/* ── SIDEBAR ── */
.sb{width:255px;flex-shrink:0;background:var(--bg-s);border-right:1px solid var(--bd);display:flex;flex-direction:column;overflow-y:auto;overflow-x:hidden;padding:10px 0 14px;transition:width .22s cubic-bezier(.4,0,.2,1)}
.sb.collapsed{width:56px}
.sb-toggle-btn{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:7px;border:1px solid var(--bd);background:transparent;cursor:pointer;color:var(--tx3);transition:all .12s;flex-shrink:0}
.sb-toggle-btn:hover{background:var(--bg-hov);color:var(--acc);border-color:var(--bd-acc)}
.sb-toggle-ico{transition:transform .22s cubic-bezier(.4,0,.2,1);display:block}
.sb.collapsed .sb-toggle-ico{transform:rotate(180deg)}
.sb-sec{padding:0 10px;margin-bottom:20px}
.sb-lbl{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.1em;text-transform:uppercase;padding:0 8px;margin-bottom:6px;white-space:nowrap;overflow:hidden;max-height:22px;opacity:1;transition:max-height .2s cubic-bezier(.4,0,.2,1),opacity .15s,margin .2s}
.sb.collapsed .sb-lbl{max-height:0;opacity:0;margin-bottom:0}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:8px;cursor:pointer;color:var(--tx2);font-size:12.5px;font-weight:500;transition:background .12s,color .12s,padding .22s,gap .22s;margin-bottom:2px;white-space:nowrap;position:relative}
.sb.collapsed .nav-item{justify-content:center;padding:9px 0;gap:0}
.nav-item:hover{background:var(--bg-hov);color:var(--tx)}
.nav-item.active{background:var(--acc-dim);color:var(--acc)}
.nav-item.active .nav-ico{opacity:1}
.nav-ico{width:16px;height:16px;flex-shrink:0;opacity:.8}
.nav-lbl{flex:1;overflow:hidden;max-width:190px;opacity:1;transition:max-width .22s cubic-bezier(.4,0,.2,1),opacity .15s}
.sb.collapsed .nav-lbl{max-width:0;opacity:0}
.nav-cnt{background:var(--c-crit);color:#fff;font-size:10px;font-weight:800;padding:1px 5px;border-radius:999px;min-width:18px;text-align:center;line-height:15px;flex-shrink:0;transition:all .15s}
.sb.collapsed .nav-cnt{position:absolute;top:3px;right:4px}
.nav-soon{font-size:9.5px;color:var(--tx3);background:var(--bg-e);padding:2px 6px;border-radius:4px;font-weight:600;overflow:hidden;max-width:56px;opacity:1;transition:max-width .2s,opacity .15s,padding .15s}
.sb.collapsed .nav-soon{max-width:0;opacity:0;padding:0}
.sb-cats-wrap{overflow:hidden;max-height:500px;opacity:1;transition:max-height .25s cubic-bezier(.4,0,.2,1),opacity .18s}
.sb.collapsed .sb-cats-wrap{max-height:0;opacity:0}
.sb-cats{display:flex;flex-direction:column;gap:2px}
.sb-cat{display:flex;align-items:center;justify-content:space-between;padding:5px 8px;border-radius:6px;cursor:pointer;transition:background .1s}
.sb-cat:hover{background:var(--bg-hov)}
.sb-cat.active{background:var(--acc-dim)}
.sb-cat.active .sb-cat-name{color:var(--acc)}
.sb-cat.active .sb-cat-n{color:var(--acc)}
.sb-cat-name{font-size:11.5px;color:var(--tx2)}
.sb-cat-n{font-size:11.5px;font-weight:700}
.sb-foot{margin-top:auto;padding:0 10px}
.sb-hint{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:11px 12px;font-size:11px;color:var(--tx3);line-height:1.55;overflow:hidden;max-height:200px;opacity:1;transition:max-height .22s,opacity .18s,padding .18s}
.sb.collapsed .sb-hint{max-height:0;opacity:0;padding:0;border-width:0}
.sb-hint b{display:block;color:var(--tx2);font-weight:600;margin-bottom:3px;font-size:11.5px}
.sb-hint .cdwn{color:var(--acc);font-weight:700;margin-top:5px}
#sb-tip{position:fixed;background:var(--bg-card);color:var(--tx);font-size:11.5px;font-weight:500;padding:5px 10px;border-radius:7px;border:1px solid var(--bd);white-space:nowrap;z-index:999;box-shadow:0 4px 14px rgba(0,0,0,.18);pointer-events:none;transition:opacity .12s;display:none}

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
.ftab.active{background:var(--bg-card);color:var(--tx);box-shadow:0 1px 4px rgba(140,118,200,.18)}
.ftab:hover:not(.active){color:var(--tx)}

/* ── BANNER ── */
.banner{background:linear-gradient(135deg,rgba(124,109,232,.07),rgba(167,139,250,.07));border:1px dashed rgba(124,109,232,.22);border-radius:10px;padding:12px 16px;display:flex;align-items:center;gap:12px}
.banner-ico{font-size:22px;flex-shrink:0}
.banner-tx{font-size:11px;color:var(--tx2);line-height:1.55}
.banner-tx strong{display:block;font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px}

/* ── TABLE ── */
.tcard{background:var(--bg-card);border:1px solid var(--bd);border-radius:12px;overflow:hidden;flex:1;min-height:0}
.twrap{overflow:auto;max-height:calc(100vh - 440px);min-height:200px}
.pager{display:flex;align-items:center;justify-content:center;gap:12px;padding:7px 12px;border-top:1px solid var(--bd);font-size:11px}
.pg-info{color:var(--tx2)}
.pg-btns{display:flex;align-items:center;gap:3px}
.pg-btn{background:var(--bg-e);border:1px solid var(--bd);border-radius:5px;padding:3px 9px;font-size:13px;cursor:pointer;color:var(--tx1);line-height:1}
.pg-btn:hover:not([disabled]){background:var(--acc);color:#fff;border-color:var(--acc)}
.pg-btn[disabled]{opacity:.3;cursor:default}
.pg-cur{padding:0 8px;color:var(--tx1);font-weight:700;font-size:11px}
table{width:100%;border-collapse:collapse}
thead th{padding:10px 14px;text-align:left;font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--bd);background:var(--bg-s);white-space:nowrap;position:sticky;top:0;z-index:2;box-shadow:0 1px 0 var(--bd)}
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
.jlnk{color:var(--acc);font-size:11px;font-weight:600}
.jlnk:hover{text-decoration:underline}
.jst{display:inline-block;font-size:9px;font-weight:700;padding:1px 5px;border-radius:8px;letter-spacing:.03em;margin-top:2px}
.jst-none{color:var(--tx3)}
.jst-todo{color:var(--c-low);background:rgba(64,104,200,.1)}
.jst-wip{color:var(--c-med);background:rgba(160,120,40,.1)}
.jst-done{color:var(--c-ok);background:rgba(56,128,104,.1)}
.btn-jira-edit{font-size:10px;padding:2px 8px;border-radius:4px;border:1px solid var(--bd);background:transparent;color:var(--tx3);cursor:pointer;margin-left:6px}
.btn-jira-edit:hover{color:var(--tx)}
.btn-jira-unlink{font-size:10px;padding:2px 8px;border-radius:4px;border:1px solid rgba(208,64,96,.35);background:transparent;color:var(--c-crit);cursor:pointer}
.btn-jira-unlink:hover{background:rgba(208,64,96,.08)}
.btn-jira-transit{font-size:10px;padding:2px 8px;border-radius:4px;border:1px solid var(--bd);background:transparent;color:var(--tx3);cursor:pointer}
.btn-jira-transit:hover{color:var(--tx)}
.transit-panel{background:var(--bg-s);border:1px solid var(--bd2);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:8px}
.transit-panel-lbl{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.08em;text-transform:uppercase}
.transit-sel{width:100%;background:var(--bg-e);border:1px solid var(--bd);border-radius:6px;padding:6px 28px 6px 10px;color:var(--tx);font-size:12px;outline:none;cursor:pointer;-webkit-appearance:none;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath fill='%23435a78' d='M5 6 0 0h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 9px center;transition:border-color .15s}
.transit-sel:focus{border-color:var(--bd-acc)}
.transit-sel option{background:var(--bg-e);color:var(--tx)}
.transit-actions{display:flex;gap:6px}
.btn-transit-apply{flex:1;display:inline-flex;align-items:center;justify-content:center;font-size:11.5px;padding:6px 0;border-radius:6px;border:none;background:var(--acc);color:#fff;cursor:pointer;font-weight:600;transition:opacity .12s;letter-spacing:.01em}
.btn-transit-apply:hover{opacity:.82}
.btn-transit-cancel{display:inline-flex;align-items:center;justify-content:center;font-size:11.5px;padding:6px 14px;border-radius:6px;border:1px solid var(--bd2);background:transparent;color:var(--tx2);cursor:pointer;font-weight:500;transition:all .12s}
.btn-transit-cancel:hover{background:var(--bg-e);color:var(--tx)}

/* ── SEVERITY ── */
.sv{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
.sv-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.sv-crit{background:rgba(208,64,96,.12);color:var(--c-crit)}.sv-crit .sv-dot{background:var(--c-crit)}
.sv-high{background:rgba(192,104,64,.11);color:var(--c-high)}.sv-high .sv-dot{background:var(--c-high)}
.sv-med{background:rgba(160,120,40,.10);color:var(--c-med)}.sv-med .sv-dot{background:var(--c-med)}
.sv-low{background:rgba(64,104,200,.10);color:var(--c-low)}.sv-low .sv-dot{background:var(--c-low)}
.sv-info{background:rgba(32,136,120,.09);color:var(--c-info)}.sv-info .sv-dot{background:var(--c-info)}
.sv-spam{background:rgba(128,112,154,.12);color:var(--c-spam)}.sv-spam .sv-dot{background:var(--c-spam)}
.sv-unk{background:rgba(128,80,184,.10);color:var(--c-fix)}.sv-unk .sv-dot{background:var(--c-fix)}

/* ── PERSONAL PRIORITY ── */
.pp{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.04em}
.pp-high{background:rgba(208,64,96,.11);color:var(--c-crit)}
.pp-med{background:rgba(160,120,40,.10);color:var(--c-med)}
.pp-low{background:rgba(64,104,200,.09);color:var(--c-low)}
.pp-none{background:rgba(128,112,154,.09);color:var(--c-spam)}
/* ── EMAIL CATEGORY ── */
.ec{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600}
.ec-urg{background:rgba(208,64,96,.11);color:var(--c-crit)}
.ec-mine{background:rgba(64,104,200,.11);color:var(--c-low)}
.ec-ref{background:rgba(32,136,120,.09);color:var(--c-info)}
.ec-ign{background:rgba(128,112,154,.10);color:var(--c-spam)}
.ec-none{background:rgba(128,112,154,.09);color:var(--c-spam)}
/* ── ACTION REQUIRED ── */
.ar-y{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(208,64,96,.11);color:var(--c-crit)}
.ar-n{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600;background:rgba(32,136,120,.09);color:var(--c-info)}
.btn-jira{padding:7px 14px;background:var(--acc);color:#fff;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .15s}
.btn-jira:hover{opacity:.85}
.btn-jira:disabled{opacity:.45;cursor:default}

/* ── STATUS ── */
.st{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:600;white-space:nowrap}
.st-new{background:rgba(128,112,154,.10);color:var(--tx2)}
.st-jira{background:rgba(124,109,232,.12);color:var(--acc)}
.st-urg{background:rgba(208,64,96,.11);color:var(--c-crit)}
.st-pulse{width:6px;height:6px;border-radius:50%;background:currentColor;animation:blink 1.4s infinite;flex-shrink:0}

/* ── SOURCE ── */
.src{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600}
.src-ol{background:rgba(64,104,200,.12);color:var(--c-low)}
.src-tm{background:rgba(124,109,232,.13);color:var(--acc)}
.src-mn{background:rgba(120,80,200,.1);color:#9060e0}

/* ── DIRECT VIEW ── */
.dtabs{display:flex;gap:4px;margin-bottom:14px}
.dtab{padding:5px 16px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;color:var(--tx2);border:1px solid transparent;transition:all .15s}
.dtab:hover{color:var(--tx1)}
.dtab.active{background:var(--bg-card);color:var(--acc);font-weight:600;border-color:var(--bd)}
.btn-add-direct{margin-bottom:12px;padding:6px 16px;background:var(--acc);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;transition:opacity .15s}
.btn-add-direct:hover{opacity:.85}
#direct-table{width:100%;border-collapse:collapse;font-size:12px}
#direct-table th{padding:8px 10px;text-align:left;color:var(--tx3);font-weight:600;border-bottom:1px solid var(--bd);white-space:nowrap}
#direct-table td{padding:8px 10px;border-bottom:1px solid var(--bd-light,var(--bd));vertical-align:middle}
#direct-table tr:hover td{background:var(--bg-e)}
.direct-actions{display:flex;gap:6px;flex-wrap:wrap}
.direct-actions button{padding:3px 9px;font-size:11px;border-radius:5px;border:1px solid var(--bd);background:var(--bg-card);color:var(--tx1);cursor:pointer;transition:background .12s}
.direct-actions button:hover{background:var(--bg-e)}
.direct-actions .btn-danger{color:#e05555;border-color:rgba(220,80,80,.3)}
.direct-actions .btn-danger:hover{background:rgba(220,80,80,.07)}
#add-direct-modal,#link-jira-modal{display:none;position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.45);align-items:center;justify-content:center}
#add-direct-modal.open,#link-jira-modal.open{display:flex}
#add-direct-modal .modal-box,#link-jira-modal .modal-box{background:var(--bg-card);border:1px solid var(--bd);border-radius:12px;padding:24px;width:420px;max-width:90vw}
#add-direct-modal h3,#link-jira-modal h3{margin:0 0 16px;font-size:15px;font-weight:700}
#add-direct-modal label,#link-jira-modal label{display:block;font-size:11px;font-weight:600;color:var(--tx2);margin-bottom:10px}
#add-direct-modal input,#add-direct-modal select,#add-direct-modal textarea,#link-jira-modal input{width:100%;box-sizing:border-box;margin-top:4px;padding:7px 10px;border:1px solid var(--bd);border-radius:6px;background:var(--bg-e);color:var(--tx1);font-size:12px}
#add-direct-modal textarea{resize:vertical}
.direct-modal-footer{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}
.direct-modal-footer button{padding:7px 18px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:none}
.direct-modal-footer .btn-ok{background:var(--acc);color:#fff}
.direct-modal-footer .btn-ok:hover{opacity:.85}
.direct-modal-footer .btn-cancel{background:var(--bg-e);color:var(--tx2);border:1px solid var(--bd)}

/* ── EMPTY ── */
.empty{padding:56px 20px;text-align:center;color:var(--tx3);font-size:12px}

/* ── DETAIL OVERLAY ── */
.ov{position:fixed;inset:0;background:rgba(80,60,140,.30);z-index:200;opacity:0;pointer-events:none;transition:opacity .2s}
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
.af-card{background:linear-gradient(135deg,rgba(124,109,232,.07),rgba(167,139,250,.07));border:1px solid rgba(124,109,232,.18);border-radius:10px;padding:14px}
.af-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.af-title{font-size:12px;font-weight:700;color:var(--acc);display:flex;align-items:center;gap:5px}
.af-badge{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:700}
.af-badge.done{background:rgba(32,136,120,.10);color:var(--c-info)}
.af-badge.pend{background:rgba(124,109,232,.12);color:var(--acc)}
.af-badge.urg{background:rgba(208,64,96,.11);color:var(--c-crit)}
.af-steps{display:flex;flex-direction:column;gap:7px}
.af-step{display:flex;align-items:center;gap:8px;font-size:11.5px}
.step-ic{width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;flex-shrink:0;line-height:1}
.ic-done{background:rgba(32,136,120,.14);color:var(--c-info)}
.ic-pend{background:rgba(140,118,200,.14);color:var(--tx3)}
.lbl-done{color:var(--tx2)}
.lbl-pend{color:var(--tx3)}
.af-prog{background:var(--bg-e);border-radius:4px;height:3px;margin-top:12px;overflow:hidden}
.af-fill{height:100%;background:linear-gradient(90deg,#7c6de8,#a78bfa);border-radius:4px;transition:width .5s}

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
.btn-analyze{padding:7px 16px;background:linear-gradient(135deg,#c04060,#8050b8);border:none;border-radius:7px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;transition:opacity .12s;display:inline-flex;align-items:center;gap:6px}
.btn-analyze:hover{opacity:.85}
.btn-analyze:disabled{opacity:.5;cursor:not-allowed}
.btn-fix{padding:7px 16px;background:linear-gradient(135deg,#2e7d52,#1f5c8b);border:none;border-radius:7px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;transition:opacity .12s;display:inline-flex;align-items:center;gap:6px}
.btn-fix:hover{opacity:.85}
.btn-fix:disabled{opacity:.5;cursor:not-allowed}
.fix-step{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--bd)}
.fix-step:last-child{border-bottom:none}
.fix-step-num{flex-shrink:0;width:20px;height:20px;border-radius:50%;background:var(--bg-e);color:var(--tx2);font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center}
.ea-result{margin-top:12px;display:flex;flex-direction:column;gap:8px;overflow:hidden}
.ea-card{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:11px 14px;overflow:hidden;min-width:0}
.ea-card table{table-layout:fixed;width:100%}
.ea-card table td{word-break:break-word;overflow-wrap:anywhere}
.ea-card-title{font-size:11px;font-weight:700;color:var(--tx3);letter-spacing:.05em;text-transform:uppercase;margin-bottom:6px}
.ea-card-body{font-size:12px;color:var(--tx);line-height:1.6;white-space:pre-wrap;word-break:break-word}
.ea-cause{display:flex;align-items:flex-start;gap:8px;padding:5px 0;border-bottom:1px solid var(--bd)}
.ea-cause:last-child{border-bottom:none}
.ea-lk{display:inline-block;padding:1px 7px;border-radius:4px;font-size:10px;font-weight:700;flex-shrink:0;margin-top:2px}
.ea-lk-h{background:rgba(208,64,96,.12);color:var(--c-crit)}
.ea-lk-m{background:rgba(160,120,40,.11);color:var(--c-med)}
.ea-lk-l{background:rgba(128,112,154,.10);color:var(--tx3)}
.btn-delete{padding:7px 16px;background:transparent;border:1px solid rgba(208,64,96,.35);border-radius:7px;color:var(--c-crit);font-size:12px;font-weight:700;cursor:pointer;transition:all .12s}
.btn-delete:hover{background:rgba(208,64,96,.08);border-color:var(--c-crit)}
.btn-row-del{background:transparent;border:none;color:rgba(208,64,96,.45);font-size:13px;cursor:pointer;padding:2px 5px;border-radius:4px;line-height:1;transition:color .1s,background .1s}
.btn-row-del:hover{color:var(--c-crit);background:rgba(208,64,96,.10)}

/* ── SETTINGS MODAL ── */
.modal-ov{position:fixed;inset:0;background:rgba(80,60,140,.30);z-index:300;display:none}
.modal-ov.open{display:block}
.settings-modal{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:440px;background:var(--bg-s);border:1px solid var(--bd2);border-radius:12px;z-index:301;display:none;flex-direction:column;box-shadow:0 8px 40px rgba(80,60,140,.20)}
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

/* ── SUMMARY / DRAFT ── */
.btn-summary{padding:7px 16px;background:linear-gradient(135deg,#7c6de8,#a78bfa);border:none;border-radius:7px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;transition:opacity .12s;display:inline-flex;align-items:center;gap:6px}
.btn-summary:hover{opacity:.85}
.btn-summary:disabled{opacity:.5;cursor:not-allowed}
.btn-draft{padding:7px 16px;background:linear-gradient(135deg,#32b88a,#7c6de8);border:none;border-radius:7px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;transition:opacity .12s;display:inline-flex;align-items:center;gap:6px}
.btn-draft:hover{opacity:.85}
.btn-draft:disabled{opacity:.5;cursor:not-allowed}
.dp-summary-text{margin-top:10px;font-size:12px;color:var(--tx);line-height:1.7;white-space:pre-wrap;word-break:break-word;background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:10px 12px}
.dp-draft-area{margin-top:10px;width:100%;min-height:130px;background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;color:var(--tx);font-size:12px;line-height:1.7;font-family:inherit;resize:vertical;outline:none;box-sizing:border-box}
.dp-draft-area:focus{border-color:var(--bd-acc)}
.btn-copy-draft{margin-top:7px;padding:5px 13px;background:transparent;border:1px solid var(--bd2);border-radius:6px;color:var(--tx2);font-size:11px;font-weight:600;cursor:pointer;transition:all .12s}
.btn-copy-draft:hover{background:var(--bg-hov);color:var(--tx)}
.dp-regen{padding:5px 10px;background:transparent;border:1px solid var(--bd2);border-radius:6px;color:var(--tx3);font-size:11px;font-weight:600;cursor:pointer;transition:all .12s}
.dp-regen:hover{color:var(--tx2);border-color:var(--bd-acc)}

/* ── STORY BUTTON ── */
.btn-story{padding:7px 14px;background:transparent;color:var(--c-fix);border:1px solid rgba(168,85,247,.35);border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;margin-top:7px}
.btn-story:hover{background:rgba(168,85,247,.1)}

/* ── STORY MODAL ── */
.story-modal{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:460px;background:var(--bg-s);border:1px solid var(--bd2);border-radius:12px;z-index:302;display:none;flex-direction:column;box-shadow:0 8px 40px rgba(80,60,140,.20)}
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
.ds-date{color-scheme:light}
html[data-theme="dark"] .ds-date{color-scheme:dark}
.dp-hi{position:absolute;opacity:0;width:1px;height:1px;pointer-events:none;overflow:hidden}
.ds-sep{color:var(--tx3);font-size:12px}
.btn-ds-search{background:var(--acc);color:#fff;border:none;border-radius:7px;padding:7px 16px;font-size:12.5px;font-weight:700;cursor:pointer;white-space:nowrap;display:inline-flex;align-items:center;justify-content:center;min-width:64px;transition:opacity .15s,transform .1s}
.btn-ds-search:not(:disabled):active{transform:scale(.96)}
.btn-ds-search:disabled{opacity:.55;cursor:default}
/* ── SEARCH LOADING ── */
#search-bar{position:fixed;top:0;left:0;right:0;height:3px;z-index:10000;pointer-events:none;opacity:0;transition:opacity .2s}
#search-bar.active{opacity:1}
#search-bar .sbar-track{position:absolute;inset:0;overflow:hidden}
#search-bar .sbar-fill{position:absolute;top:0;left:-60%;width:60%;height:100%;background:linear-gradient(90deg,transparent,var(--acc),var(--acc-dim),var(--acc),transparent);animation:sbar-run .9s ease-in-out infinite}
@keyframes sbar-run{0%{left:-60%}100%{left:110%}}
#center-loader{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%) scale(.9);background:var(--bg-card);border:1px solid var(--bd);border-radius:14px;padding:14px 22px;display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600;color:var(--tx);box-shadow:0 8px 32px rgba(0,0,0,.2);z-index:9999;opacity:0;pointer-events:none;transition:opacity .18s,transform .18s}
#center-loader.active{opacity:1;pointer-events:auto;transform:translate(-50%,-50%) scale(1)}
.cl-spinner{width:16px;height:16px;border:2.5px solid var(--bd);border-top-color:var(--acc);border-radius:50%;animation:spin .55s linear infinite;flex-shrink:0}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── CUSTOM DATE PICKER ── */
.calpick{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;cursor:pointer;font-size:12.5px;color:var(--tx);transition:all .15s;user-select:none;white-space:nowrap;position:relative}
.calpick:hover{border-color:var(--bd-acc)}
.calpick.dp-active{border-color:var(--acc);background:var(--acc-dim)}
.calpick-ico{color:var(--acc);flex-shrink:0;opacity:.75}
[id^="dp-lbl-"]{display:inline-block;min-width:72px}
.dp-popup{position:fixed;z-index:9999;background:var(--bg-card);border:1px solid var(--bd2);border-radius:13px;box-shadow:0 12px 40px rgba(0,0,0,.2);padding:16px;width:276px;display:none}
.dp-popup.open{display:block}
.dp-tgt{font-size:10px;font-weight:700;color:var(--acc);background:var(--acc-dim);border-radius:5px;padding:3px 10px;text-align:center;margin-bottom:10px;letter-spacing:.06em;text-transform:uppercase}
.dp-phdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.dp-nav-b{background:var(--bg-e);border:1px solid var(--bd);border-radius:6px;width:28px;height:28px;font-size:16px;cursor:pointer;color:var(--tx2);display:flex;align-items:center;justify-content:center;line-height:1;transition:all .12s}
.dp-nav-b:hover{background:var(--acc);color:#fff;border-color:var(--acc)}
.dp-ttl{font-size:13px;font-weight:700;color:var(--tx)}
.dp-wk{display:grid;grid-template-columns:repeat(7,1fr);text-align:center;font-size:10px;font-weight:700;color:var(--tx3);margin-bottom:5px}
.dp-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:2px}
.dp-cell{text-align:center;padding:5px 2px;font-size:12px;border-radius:5px;color:var(--tx);cursor:pointer;transition:background .1s,color .1s;line-height:1.5}
.dp-cell.empty{cursor:default}
.dp-cell:not(.empty):not(.dp-sel):hover{background:var(--acc-dim);color:var(--acc)}
.dp-today{font-weight:800;color:var(--acc)}
.dp-today::after{content:"·";display:block;font-size:8px;line-height:.2;color:var(--acc)}
.dp-sel{background:var(--acc);color:#fff !important;font-weight:700}
.dp-sel-start{border-radius:5px 0 0 5px}
.dp-sel-end{border-radius:0 5px 5px 0}
.dp-sel-start.dp-sel-end{border-radius:5px !important}
.dp-range{background:var(--acc-dim);color:var(--acc);border-radius:0}
.dp-sun{color:var(--c-crit)}
.dp-sat{color:var(--c-info)}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:2px}
::-webkit-scrollbar-thumb:hover{background:var(--tx3)}

/* ── REPORT VIEW ── */
.rpt-page{padding:20px 28px}
.gf-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px;background:var(--bg-card);border:1px solid var(--bd);border-left:3px solid var(--acc);border-radius:10px;padding:10px 16px}
.gf-lbl{font-size:10px;font-weight:800;color:var(--tx3);letter-spacing:.09em;text-transform:uppercase;flex-shrink:0}
.rng-presets{display:flex;gap:2px;margin-left:4px;padding-left:8px;border-left:1px solid var(--bd)}
.rng-btn{background:transparent;border:1px solid var(--bd);border-radius:6px;padding:4px 10px;font-size:11.5px;font-weight:600;color:var(--tx2);cursor:pointer;transition:all .12s;white-space:nowrap;font-family:inherit}
.rng-btn:hover{background:var(--acc-dim);border-color:var(--acc);color:var(--acc)}
.rtabs{display:flex;gap:2px;margin-bottom:16px;background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:4px}
.rtab{flex:1;padding:8px 10px;border:none;background:transparent;color:var(--tx2);font-size:12px;font-weight:600;border-radius:7px;cursor:pointer;transition:all .12s;white-space:nowrap}
.rtab.active{background:var(--bg-s);color:var(--tx);box-shadow:0 1px 4px rgba(140,118,200,.18)}
.rtab:hover:not(.active){color:var(--tx)}
.sum-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.sum-card{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:16px 18px;position:relative;overflow:hidden}
.sum-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2.5px;border-radius:10px 10px 0 0;background:var(--acc)}
.sum-card-warn::before{background:var(--c-crit)}
.sum-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:8px}
.sum-val{font-size:28px;font-weight:900;letter-spacing:-.04em;line-height:1;color:var(--tx)}
.sum-card-warn .sum-val{color:var(--c-crit)}
.sum-desc{font-size:10.5px;color:var(--tx3);margin-top:4px}
.unproc-banner{background:linear-gradient(135deg,rgba(208,64,96,.06),rgba(124,109,232,.06));border:1px dashed rgba(208,64,96,.22);border-radius:10px;padding:13px 18px;display:flex;align-items:center;gap:12px;cursor:pointer;transition:background .12s}
.unproc-banner:hover{background:linear-gradient(135deg,rgba(208,64,96,.10),rgba(124,109,232,.10))}
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
.jbadge-yes{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(32,136,120,.10);color:var(--c-info)}
.jbadge-no{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(208,64,96,.10);color:var(--c-crit)}
.jlnk{color:var(--acc);font-size:11px;font-weight:600}
.jlnk:hover{text-decoration:underline}
.overdue-hi{color:var(--c-crit);font-weight:700}
.overdue-md{color:var(--c-med);font-weight:700}
.overdue-lo{color:var(--tx2);font-weight:600}
.hist-filter{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:10px}
.md-panel{position:fixed;right:0;top:0;bottom:0;width:440px;background:var(--bg-s);border-left:3px solid var(--acc);box-shadow:-8px 0 36px rgba(80,60,140,.18);z-index:305;transform:translateX(100%);transition:transform .22s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden}
.md-panel.open{transform:translateX(0)}
.md-hdr{padding:16px 20px;border-bottom:1px solid var(--bd2);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:10px}
.md-hdr-title{font-size:13.5px;font-weight:700;color:var(--tx);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.md-hdr button{background:rgba(124,109,232,.08);border:none;color:var(--tx2);font-size:15px;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.md-body{flex:1;overflow-y:auto;padding:18px 20px;display:flex;flex-direction:column;gap:10px}
.dp-field{background:rgba(124,109,232,.05);border:1px solid var(--bd);border-radius:8px;padding:9px 11px}
.dp-field-lbl{font-size:10px;color:var(--tx3);margin-bottom:3px;font-weight:600;letter-spacing:.04em}
.dp-field-val{font-size:12px;color:var(--tx);font-weight:500;word-break:break-all}
.dp-body-text{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;font-size:11.5px;color:var(--tx2);line-height:1.65;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto}
.spinner-wrap{display:flex;justify-content:center;padding:36px}
.spin{width:26px;height:26px;border:3px solid var(--bd2);border-top-color:var(--acc);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── DARK THEME OVERRIDES ── */
html[data-theme="dark"] .logo{background:linear-gradient(135deg,#1a4fff,#0ea5e9);box-shadow:0 2px 12px rgba(43,109,255,.4)}
html[data-theme="dark"] thead th{background:var(--bg-s)}
html[data-theme="dark"] .ftab.active{box-shadow:0 1px 4px rgba(0,0,0,.35)}
html[data-theme="dark"] .rtab.active{box-shadow:0 1px 4px rgba(0,0,0,.4)}
html[data-theme="dark"] .ov{background:rgba(0,0,0,.55)}
html[data-theme="dark"] .modal-ov{background:rgba(0,0,0,.55)}
html[data-theme="dark"] .settings-modal{box-shadow:0 8px 40px rgba(0,0,0,.5)}
html[data-theme="dark"] .story-modal{box-shadow:0 8px 40px rgba(0,0,0,.5)}
html[data-theme="dark"] .md-panel{background:#14274d;box-shadow:-8px 0 36px rgba(0,0,0,.7)}
html[data-theme="dark"] .md-hdr button{background:rgba(255,255,255,.07)}
html[data-theme="dark"] .dp-field{background:rgba(255,255,255,.05);border-color:rgba(255,255,255,.10)}
html[data-theme="dark"] .jlnk{color:#ffc94d}
html[data-theme="dark"] .btn-jira-unlink{border-color:rgba(255,68,68,.4);color:#ff7070}
html[data-theme="dark"] .btn-jira-unlink:hover{background:rgba(255,68,68,.08)}
html[data-theme="dark"] .transit-sel option{background:#0e1d38}
html[data-theme="dark"] .banner{background:linear-gradient(135deg,rgba(43,109,255,.07),rgba(168,85,247,.07));border-color:rgba(43,109,255,.22)}
html[data-theme="dark"] .af-card{background:linear-gradient(135deg,rgba(168,85,247,.07),rgba(43,109,255,.07));border-color:rgba(168,85,247,.22)}
html[data-theme="dark"] .af-title{color:#b07fff}
html[data-theme="dark"] .af-badge.done{background:rgba(46,202,138,.12);color:#4cd9a0}
html[data-theme="dark"] .af-badge.pend{background:rgba(168,85,247,.15);color:#c090ff}
html[data-theme="dark"] .af-badge.urg{background:rgba(255,68,68,.12);color:#ff7070}
html[data-theme="dark"] .ic-done{background:rgba(46,202,138,.18);color:#4cd9a0}
html[data-theme="dark"] .ic-pend{background:rgba(67,90,120,.2);color:#435a78}
html[data-theme="dark"] .af-fill{background:linear-gradient(90deg,#a855f7,#2b6dff)}
html[data-theme="dark"] .sv-crit{background:rgba(255,68,68,.11);color:#ff7070}
html[data-theme="dark"] .sv-crit .sv-dot{background:#ff4444}
html[data-theme="dark"] .sv-high{background:rgba(255,122,41,.11);color:#ffaa70}
html[data-theme="dark"] .sv-high .sv-dot{background:#ff7a29}
html[data-theme="dark"] .sv-med{background:rgba(255,184,32,.1);color:#ffce60}
html[data-theme="dark"] .sv-med .sv-dot{background:#ffb820}
html[data-theme="dark"] .sv-low{background:rgba(74,144,255,.11);color:#80b6ff}
html[data-theme="dark"] .sv-low .sv-dot{background:#4a90ff}
html[data-theme="dark"] .sv-info{background:rgba(56,217,196,.09);color:#38d9c4}
html[data-theme="dark"] .sv-info .sv-dot{background:#38d9c4}
html[data-theme="dark"] .sv-spam{background:rgba(67,90,120,.15);color:#6a8299}
html[data-theme="dark"] .sv-spam .sv-dot{background:#6a8299}
html[data-theme="dark"] .sv-unk{background:rgba(168,85,247,.1);color:#c090ff}
html[data-theme="dark"] .sv-unk .sv-dot{background:#a855f7}
html[data-theme="dark"] .pp-high{background:rgba(255,68,68,.13);color:#ff7070}
html[data-theme="dark"] .pp-med{background:rgba(255,184,32,.11);color:#ffce60}
html[data-theme="dark"] .pp-low{background:rgba(74,144,255,.1);color:#80b6ff}
html[data-theme="dark"] .pp-none{background:rgba(100,120,150,.1);color:#6a8299}
html[data-theme="dark"] .ec-urg{background:rgba(255,68,68,.13);color:#ff7070}
html[data-theme="dark"] .ec-mine{background:rgba(43,109,255,.13);color:#6b9fff}
html[data-theme="dark"] .ec-ref{background:rgba(56,217,196,.1);color:#38d9c4}
html[data-theme="dark"] .ec-ign{background:rgba(67,90,120,.14);color:#6a8299}
html[data-theme="dark"] .ec-none{background:rgba(100,120,150,.1);color:#6a8299}
html[data-theme="dark"] .ar-y{background:rgba(255,68,68,.12);color:#ff8080}
html[data-theme="dark"] .ar-n{background:rgba(56,217,196,.08);color:#38d9c4}
html[data-theme="dark"] .st-new{background:rgba(139,163,194,.1);color:#8ba3c2}
html[data-theme="dark"] .st-jira{background:rgba(255,201,77,.1);color:#ffc94d}
html[data-theme="dark"] .st-urg{background:rgba(255,68,68,.11);color:#ff7070}
html[data-theme="dark"] .src-ol{background:rgba(0,114,198,.15);color:#5aacff}
html[data-theme="dark"] .src-tm{background:rgba(97,66,196,.15);color:#a07aff}
html[data-theme="dark"] .src-mn{background:rgba(120,80,200,.15);color:#b07aff}
html[data-theme="dark"] .jbadge-yes{background:rgba(46,202,138,.12);color:#4cd9a0}
html[data-theme="dark"] .jbadge-no{background:rgba(255,68,68,.12);color:#ff7070}
html[data-theme="dark"] .jst-todo{color:#5b9ef7;background:rgba(43,109,255,.12)}
html[data-theme="dark"] .jst-wip{color:#ffb820;background:rgba(255,184,32,.1)}
html[data-theme="dark"] .jst-done{color:#2eca8a;background:rgba(46,202,138,.1)}
html[data-theme="dark"] .btn-analyze{background:linear-gradient(135deg,#e53935,#b71c1c)}
html[data-theme="dark"] .btn-fix{background:linear-gradient(135deg,#2e9e63,#1e6fa8)}
html[data-theme="dark"] .btn-summary{background:linear-gradient(135deg,#0ea5e9,#1a4fff)}
html[data-theme="dark"] .btn-draft{background:linear-gradient(135deg,#2eca8a,#0ea5e9)}
html[data-theme="dark"] .btn-story{color:#a855f7;border-color:rgba(168,85,247,.35)}
html[data-theme="dark"] .btn-story:hover{background:rgba(168,85,247,.1)}
html[data-theme="dark"] .ea-lk-h{background:rgba(255,68,68,.15);color:#ff7070}
html[data-theme="dark"] .ea-lk-m{background:rgba(255,165,0,.15);color:#ffb347}
html[data-theme="dark"] .btn-delete{border-color:rgba(255,68,68,.4);color:#ff7070}
html[data-theme="dark"] .btn-delete:hover{background:rgba(255,68,68,.1);border-color:#ff7070}
html[data-theme="dark"] .btn-row-del{color:rgba(255,112,112,.5)}
html[data-theme="dark"] .btn-row-del:hover{color:#ff7070;background:rgba(255,68,68,.12)}
html[data-theme="dark"] .unproc-banner{background:linear-gradient(135deg,rgba(255,68,68,.07),rgba(43,109,255,.07));border-color:rgba(255,68,68,.25)}
html[data-theme="dark"] .unproc-banner:hover{background:linear-gradient(135deg,rgba(255,68,68,.12),rgba(43,109,255,.12))}
html[data-theme="dark"] .nav-cnt{background:var(--c-crit)}

/* ── RESPONSIVE ── */
table{min-width:560px}
@media (max-width:1100px){
  .stats{grid-template-columns:repeat(3,1fr)}
  .sum-cards{grid-template-columns:repeat(3,1fr)}
}
@media (max-width:900px){
  .sum-cards{grid-template-columns:repeat(2,1fr)}
  .chart-row{grid-template-columns:1fr}
}
@media (max-width:768px){
  .sb{position:fixed;left:0;top:58px;bottom:0;z-index:150;width:255px !important;transform:translateX(-100%);box-shadow:6px 0 32px rgba(30,10,60,.22)}
  .sb.collapsed,.sb.sb-mobile-open.collapsed{width:255px !important;transform:translateX(-100%)}
  .sb.sb-mobile-open{transform:translateX(0)}
  .sb.sb-mobile-open .sb-lbl{max-height:22px;opacity:1;margin-bottom:6px}
  .sb.sb-mobile-open .sb-toggle-ico{transform:rotate(180deg)}
  .sb.sb-mobile-open .nav-item{justify-content:flex-start;padding:8px 10px;gap:9px}
  .sb.sb-mobile-open .nav-lbl{max-width:190px;opacity:1}
  .sb.sb-mobile-open .nav-cnt{position:static}
  .sb.sb-mobile-open .nav-soon{max-width:56px;opacity:1;padding:2px 6px}
  .sb.sb-mobile-open .sb-cats-wrap{max-height:500px;opacity:1}
  .sb.sb-mobile-open .sb-hint{max-height:200px;opacity:1;padding:11px 12px;border-width:1px}
  .sb-bd{display:none;position:fixed;inset:0;top:58px;background:rgba(20,8,48,.45);z-index:149}
  .sb-bd.open{display:block}
  .hdr-l{border-right:none;width:auto !important}
  .hdr.sb-collapsed .hdr-l{width:auto !important}
  .logo{max-width:43px !important;opacity:1 !important}
  .hdr-titles{max-width:none !important;opacity:1 !important}
  .hdr-co{display:none}
  .hdr-sys{font-size:12.5px}
  .clock,.last-upd{display:none}
  .main-in{padding:12px 12px;gap:11px}
  .stats{grid-template-columns:repeat(2,1fr);gap:8px}
  .sc-val{font-size:22px}
  .pg-hdr{flex-wrap:wrap;gap:8px}
  .frow{gap:6px}
  .srch-wrap{flex:1 1 100%;max-width:100%;min-width:0}
  .twrap{max-height:calc(100vh - 280px)}
  .dp{width:100vw}
  .settings-modal{width:94vw;max-width:440px}
  .story-modal{width:94vw;max-width:460px}
  .avg-card{min-width:100px}
}
@media (max-width:480px){
  .stats{grid-template-columns:repeat(2,1fr);gap:6px}
  .sc-val{font-size:20px}
  .sc-desc{display:none}
  .main-in{padding:10px 10px;gap:9px}
  .twrap{max-height:calc(100vh - 258px)}
  .hdr-r{gap:8px}
  .live{display:none}
}

/* ── CUSTOM NOTIFICATION / CONFIRM SYSTEM ── */
#notif-wrap{position:fixed;top:72px;left:50%;transform:translateX(-50%);z-index:9000;display:flex;flex-direction:column;align-items:center;gap:8px;pointer-events:none;min-width:0}
.notif-item{pointer-events:auto;min-width:300px;max-width:440px;background:var(--bg-card);border:1px solid var(--bd2);border-radius:12px;padding:13px 16px;display:flex;align-items:flex-start;gap:11px;box-shadow:0 8px 32px rgba(0,0,0,.18);animation:notif-in .24s cubic-bezier(.34,1.56,.64,1) both;position:relative;overflow:hidden}
.notif-item.leaving{animation:notif-out .2s cubic-bezier(.4,0,.2,1) both}
@keyframes notif-in{from{opacity:0;transform:translateY(-18px) scale(.92)}to{opacity:1;transform:none}}
@keyframes notif-out{to{opacity:0;transform:translateY(-10px) scale(.95)}}
.notif-icon{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;flex-shrink:0;margin-top:1px}
.notif-body{flex:1;min-width:0}
.notif-title{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:2px}
.notif-msg{font-size:12.5px;color:var(--tx);font-weight:500;line-height:1.5;word-break:break-word}
.notif-close{background:none;border:none;color:var(--tx3);font-size:12px;cursor:pointer;padding:2px 4px;line-height:1;flex-shrink:0;transition:color .1s;align-self:flex-start}
.notif-close:hover{color:var(--tx)}
.notif-progress{position:absolute;bottom:0;left:0;height:2.5px;background:currentColor;animation:notif-prog linear forwards}
@keyframes notif-prog{from{width:100%}to{width:0}}
.notif-item.n-err{border-color:rgba(208,64,96,.28)}.notif-item.n-err .notif-icon{background:rgba(208,64,96,.13);color:var(--c-crit)}.notif-item.n-err .notif-progress{color:var(--c-crit)}
.notif-item.n-ok{border-color:rgba(32,136,120,.28)}.notif-item.n-ok .notif-icon{background:rgba(32,136,120,.13);color:var(--c-ok)}.notif-item.n-ok .notif-progress{color:var(--c-ok)}
.notif-item.n-warn{border-color:rgba(160,120,40,.28)}.notif-item.n-warn .notif-icon{background:rgba(160,120,40,.12);color:var(--c-med)}.notif-item.n-warn .notif-progress{color:var(--c-med)}
.notif-item.n-info{border-color:var(--bd-acc)}.notif-item.n-info .notif-icon{background:var(--acc-dim);color:var(--acc)}.notif-item.n-info .notif-progress{color:var(--acc)}
/* cm = custom modal (alert / confirm / prompt) */
.cm-ov{position:fixed;inset:0;z-index:9100;background:rgba(40,20,90,.38);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .18s}
.cm-ov.open{opacity:1;pointer-events:all}
.cm-box{background:var(--bg-s);border:1px solid var(--bd2);border-radius:18px;padding:30px 26px 22px;min-width:280px;max-width:390px;width:88vw;box-shadow:0 24px 64px rgba(0,0,0,.22);transform:scale(.88) translateY(18px);transition:transform .28s cubic-bezier(.34,1.56,.64,1),opacity .18s;opacity:0;overflow:hidden}
.cm-ov.open .cm-box{transform:none;opacity:1}
.cm-icon-wrap{width:54px;height:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;margin:0 auto 16px;flex-shrink:0}
.cm-icon-err{background:rgba(208,64,96,.12)}.cm-icon-warn{background:rgba(160,120,40,.12)}
.cm-icon-ok{background:rgba(32,136,120,.12)}.cm-icon-del{background:rgba(208,64,96,.12)}.cm-icon-info{background:var(--acc-dim)}
.cm-title{font-size:15.5px;font-weight:800;color:var(--tx);text-align:center;margin-bottom:8px;letter-spacing:-.03em;line-height:1.3}
.cm-msg{font-size:12.5px;color:var(--tx2);text-align:center;line-height:1.65;margin-bottom:20px;word-break:break-word;white-space:pre-wrap;min-height:1px}
.cm-btns{display:flex;gap:8px;margin-top:4px}
.cm-btn-cancel{flex:1;padding:10px;border-radius:9px;border:1px solid var(--bd2);background:transparent;color:var(--tx2);font-size:13px;font-weight:600;cursor:pointer;transition:all .12s;font-family:inherit}
.cm-btn-cancel:hover{background:var(--bg-hov);color:var(--tx)}
.cm-btn-ok{flex:1;padding:10px;border-radius:9px;border:none;background:var(--acc);color:#fff;font-size:13px;font-weight:700;cursor:pointer;transition:opacity .12s;font-family:inherit;letter-spacing:.01em}
.cm-btn-ok:hover{opacity:.85}
.cm-btn-ok.danger{background:var(--c-crit)}
.cm-input{width:100%;background:var(--bg-e);border:1px solid var(--bd2);border-radius:9px;padding:9px 12px;color:var(--tx);font-size:13px;outline:none;margin-bottom:16px;box-sizing:border-box;font-family:inherit;transition:border-color .15s}
.cm-input:focus{border-color:var(--acc)}
.cm-list{display:flex;flex-direction:column;gap:4px;margin-bottom:16px;max-height:210px;overflow-y:auto}
.cm-list-item{padding:10px 13px;border-radius:8px;cursor:pointer;font-size:13px;color:var(--tx2);border:1px solid var(--bd);transition:all .12s;user-select:none}
.cm-list-item:hover{background:var(--acc-dim);color:var(--acc);border-color:var(--bd-acc)}
.cm-list-item.cm-selected{background:var(--acc-dim);color:var(--acc);border-color:var(--acc);font-weight:600}
html[data-theme="dark"] .cm-ov{background:rgba(0,0,0,.55)}
html[data-theme="dark"] .cm-box{box-shadow:0 24px 64px rgba(0,0,0,.65)}
html[data-theme="dark"] .notif-item{box-shadow:0 8px 32px rgba(0,0,0,.45)}
html[data-theme="dark"] .notif-item.n-err{border-color:rgba(255,68,68,.3)}
html[data-theme="dark"] .notif-item.n-ok{border-color:rgba(46,202,138,.3)}
html[data-theme="dark"] .notif-item.n-warn{border-color:rgba(255,184,32,.3)}

/* ── SENDER HISTORY ── */
.sh-stats{display:flex;gap:6px;margin-bottom:10px}
.sh-stat{background:var(--bg-e);border:1px solid var(--bd);border-radius:8px;padding:8px 10px;flex:1;text-align:center}
.sh-stat-val{font-size:18px;font-weight:800;color:var(--tx);letter-spacing:-.03em;line-height:1}
.sh-stat-lbl{font-size:9.5px;font-weight:700;color:var(--tx3);margin-top:3px;letter-spacing:.05em;text-transform:uppercase}
.sh-table{width:100%;border-collapse:collapse;font-size:11.5px}
.sh-table th{padding:5px 7px;text-align:left;font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;border-bottom:1px solid var(--bd)}
.sh-table td{padding:5px 7px;border-bottom:1px solid var(--bd);vertical-align:middle}
.sh-table tr:last-child td{border-bottom:none}
.sh-table tr:hover td{background:var(--bg-hov);cursor:pointer}
.sh-subj{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--tx);font-weight:500}
.sh-none{font-size:11.5px;color:var(--tx3);padding:6px 0}
/* ── NL SEARCH ── */
.btn-nl-search{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:7px;border:1px solid var(--bd-acc);background:var(--acc-dim);color:var(--acc);font-size:12px;font-weight:700;cursor:pointer;transition:all .12s;font-family:inherit;white-space:nowrap;flex-shrink:0}
.btn-nl-search:hover,.btn-nl-search.active{background:var(--acc);color:#fff;border-color:var(--acc)}
.nl-badge{display:none;align-items:center;gap:6px;background:var(--acc-dim);border:1px solid var(--bd-acc);border-radius:7px;padding:5px 10px;font-size:11.5px;font-weight:600;color:var(--acc);flex-shrink:0}
.nl-badge.visible{display:inline-flex}
.nl-badge-close{background:none;border:none;color:var(--acc);cursor:pointer;font-size:13px;padding:0 2px;line-height:1;font-weight:900;transition:opacity .1s}
.nl-badge-close:hover{opacity:.6}
html[data-theme="dark"] .btn-nl-search{border-color:rgba(43,109,255,.4);background:rgba(43,109,255,.12);color:#6b9fff}
html[data-theme="dark"] .btn-nl-search:hover,.btn-nl-search.active{background:#2b6dff;color:#fff}
html[data-theme="dark"] .nl-badge{border-color:rgba(43,109,255,.35);background:rgba(43,109,255,.12);color:#6b9fff}
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
    <button id="hdr-sb-btn" class="sb-toggle-btn" onclick="toggleSidebar()" title="사이드바 접기/펼치기">
      <svg class="sb-toggle-ico" width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M9 2L4 7l5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  </div>
  <div class="hdr-r">
    <div class="live"><div class="live-dot"></div>LIVE</div>
    <span class="last-upd" id="last-upd">갱신 대기 중</span>
    <button class="btn btn-ghost" id="btn-theme" onclick="toggleTheme()" title="테마 변경" style="padding:5px 8px;display:inline-flex;align-items:center;justify-content:center;width:32px;height:28px"><svg id="theme-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></button>
    <button class="btn btn-ghost" id="btn-settings" onclick="openSettings()" title="개인 설정" style="padding:5px 10px;font-size:16px;line-height:1">&#9881;</button>
    <span class="clock" id="clock">--:--:--</span>
  </div>
</header>

<div class="wrap">
  <aside class="sb" id="sidebar">
    <div class="sb-sec" style="margin-top:8px">
      <div class="sb-lbl">모니터링</div>
      <div class="nav-item active" id="nav-today" onclick="showView('today')" data-tip="인바운드 현황">
        <svg class="nav-ico" viewBox="0 0 16 16" fill="none">
          <path d="M2 11l3.5-4 3 3L12 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="13.5" cy="11.5" r="2" fill="currentColor"/>
        </svg>
        <span class="nav-lbl">인바운드 현황</span>
        <span class="nav-cnt" id="crit-cnt" style="display:none">0</span>
      </div>
      <div class="nav-item" style="opacity:.45;pointer-events:none" data-tip="자동 수정">
        <svg class="nav-ico" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.5"/>
          <path d="M8 5v3l2 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span class="nav-lbl">자동 수정</span>
        <span class="nav-soon">준비중</span>
      </div>
      <div class="nav-item" id="nav-report" onclick="showView('report')" data-tip="리포트">
        <svg class="nav-ico" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
          <path d="M5 7h6M5 10h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span class="nav-lbl">리포트</span>
      </div>
    </div>

    <div class="sb-sec">
      <div class="sb-lbl">분류별 건수</div>
      <div class="sb-cats-wrap">
        <div class="sb-cats" id="sb-cats"></div>
      </div>
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
        <div style="display:flex;gap:8px;align-items:center">
          <button class="btn btn-ghost" onclick="openAddDirectModal()">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="2" width="12" height="12" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
              <path d="M8 5v6M5 8h6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            직접 등록
          </button>
          <button class="btn btn-ghost" onclick="fetchAndRender()">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
              <path d="M13.5 8A5.5 5.5 0 002.5 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              <path d="M2.5 8a5.5 5.5 0 0011 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-dasharray="2 3"/>
              <path d="M13.5 4.5l.5 3.5-3.5-.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            새로고침
          </button>
        </div>
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
          <div class="ftab" data-src="manual">수동생성</div>
        </div>
        <span style="color:var(--tx3);font-size:12px;padding:0 2px">|</span>
        <div class="calpick" id="dpf-start" onclick="dpOpen('start')">
          <svg class="calpick-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          <span id="dp-lbl-start">오늘</span>
          <input type="date" class="ds-date dp-hi" id="ds-start">
        </div>
        <span class="ds-sep">~</span>
        <div class="calpick" id="dpf-end" onclick="dpOpen('end')">
          <svg class="calpick-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          <span id="dp-lbl-end">오늘</span>
          <input type="date" class="ds-date dp-hi" id="ds-end">
        </div>
        <button class="btn-ds-search" onclick="runDateSearch()">검색</button>
        <button class="btn btn-ghost" onclick="resetToToday()" style="font-size:12.5px;padding:8px 16px">오늘</button>
        <button class="btn btn-ghost" onclick="setDsRange('week')" style="font-size:12.5px;padding:8px 16px">이번 주</button>
        <button class="btn btn-ghost" onclick="setDsRange('month')" style="font-size:12.5px;padding:8px 16px">이번 달</button>
        <button class="btn-nl-search" id="btn-nl-search" onclick="toggleNLSearch()">&#129302; AI 검색</button>
        <div class="nl-badge" id="nl-badge"><span id="nl-badge-text"></span><button class="nl-badge-close" onclick="clearNLSearch()">&#10005;</button></div>
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
        <div id="pager" class="pager"></div>
      </div>

    </div><!-- /main-in -->

    <!-- ── 직접 등록 뷰 ── -->
    <div id="direct-view" class="main-in" style="display:none">
      <div class="pg-hdr">
        <div class="pg-title">직접 등록</div>
        <div class="pg-sub">Outlook / Teams 메시지 또는 수동으로 생성한 항목의 Jira 티켓을 직접 관리합니다.</div>
      </div>
      <div class="dtabs">
        <div class="dtab active" data-dtab="outlook" onclick="switchDirectTab('outlook')">Outlook</div>
        <div class="dtab" data-dtab="teams"   onclick="switchDirectTab('teams')">Teams</div>
        <div class="dtab" data-dtab="manual"  onclick="switchDirectTab('manual')">수동생성</div>
      </div>
      <button class="btn-add-direct" onclick="openAddDirectModal()">+ 새 항목</button>
      <table id="direct-table">
        <thead>
          <tr>
            <th>제목</th><th>발신자</th><th>출처</th>
            <th>Jira</th><th>등록일</th><th>액션</th>
          </tr>
        </thead>
        <tbody id="direct-tbody">
          <tr><td colspan="6" style="text-align:center;color:var(--tx3);padding:32px">항목이 없습니다.</td></tr>
        </tbody>
      </table>

    </div><!-- /direct-view -->

    <div id="report-view" style="display:none">
      <div class="rpt-page">

        <!-- 공통 날짜 필터 -->
        <div class="gf-bar">
          <span class="gf-lbl">조회 기간</span>
          <div class="calpick" id="dpf-r-start" onclick="dpOpen('start','r')">
            <svg class="calpick-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            <span id="dp-lbl-r-start">이번 달 시작</span>
            <input type="date" class="ds-date dp-hi" id="r-start">
          </div>
          <span class="ds-sep">~</span>
          <div class="calpick" id="dpf-r-end" onclick="dpOpen('end','r')">
            <svg class="calpick-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            <span id="dp-lbl-r-end">오늘</span>
            <input type="date" class="ds-date dp-hi" id="r-end">
          </div>
          <button class="btn-ds-search" onclick="doSearch(true)">검색</button>
          <div class="rng-presets">
            <button class="rng-btn" onclick="setRange('today')">오늘</button>
            <button class="rng-btn" onclick="setRange('week')">이번 주</button>
            <button class="rng-btn" onclick="setRange('month')">이번 달</button>
          </div>
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

<div id="search-bar"><div class="sbar-track"><div class="sbar-fill"></div></div></div>
<div id="center-loader"><div class="cl-spinner"></div><span>검색 중...</span></div>

<div id="dp-popup" class="dp-popup">
  <div class="dp-tgt" id="dp-tgt-lbl">시작일 선택</div>
  <div class="dp-phdr">
    <button class="dp-nav-b" onclick="dpMove(-1)">&#8249;</button>
    <span class="dp-ttl" id="dp-ttl"></span>
    <button class="dp-nav-b" onclick="dpMove(1)">&#8250;</button>
  </div>
  <div class="dp-wk">
    <span style="color:var(--c-crit)">일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span style="color:var(--c-info)">토</span>
  </div>
  <div class="dp-grid" id="dp-grid"></div>
</div>

<div id="add-direct-modal">
  <div class="modal-box">
    <h3>항목 직접 등록</h3>
    <label>출처
      <select id="add-src">
        <option value="outlook">Outlook</option>
        <option value="teams">Teams</option>
        <option value="manual">수동생성</option>
      </select>
    </label>
    <label>제목 / 티켓명
      <input id="add-subject" type="text" placeholder="메시지 제목 또는 Jira 티켓명">
    </label>
    <label>발신자
      <input id="add-sender" type="text" placeholder="이메일 또는 이름 (선택)">
    </label>
    <label>내용
      <textarea id="add-body" rows="4" placeholder="메시지 본문 또는 설명"></textarea>
    </label>
    <div class="direct-modal-footer">
      <button class="btn-cancel" onclick="closeAddDirectModal()">취소</button>
      <button class="btn-ok" onclick="submitAddDirect()">등록</button>
    </div>
  </div>
</div>

<div id="link-jira-modal">
  <div class="modal-box">
    <h3>기존 Jira 키 연결</h3>
    <label>Jira 키 (예: GW-123)
      <input id="link-jira-key" type="text" placeholder="PROJECT-000">
    </label>
    <div class="direct-modal-footer">
      <button class="btn-cancel" onclick="closeLinkJiraModal()">취소</button>
      <button class="btn-ok" onclick="submitLinkJira()">연결</button>
    </div>
  </div>
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
    <div id="dp-sender-hist" style="display:none">
      <div class="dp-sec-lbl">발신자 이력</div>
      <div class="sh-stats" id="sh-stats-wrap" style="display:none">
        <div class="sh-stat"><div class="sh-stat-val" id="sh-total">0</div><div class="sh-stat-lbl">총 수신</div></div>
        <div class="sh-stat"><div class="sh-stat-val" id="sh-urgent" style="color:var(--c-crit)">0</div><div class="sh-stat-lbl">긴급</div></div>
        <div class="sh-stat"><div class="sh-stat-val" id="sh-avg" style="color:var(--c-ok)">-</div><div class="sh-stat-lbl">평균처리</div></div>
      </div>
      <div id="sh-list"></div>
      <div class="sh-none" id="sh-loading">&#8203;</div>
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
          <label class="dp-field-lbl">액션 필요</label>
          <select class="dp-select" id="dp-edit-ar">
            <option value="">&#8212;</option>
            <option value="true">필요</option>
            <option value="false">불필요</option>
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
        <div class="dp-field"><div class="dp-field-lbl">티켓 키</div><div class="dp-field-val"><a id="dp-jira-lnk" href="#" target="_blank" class="jlnk"></a><button class="btn-jira-edit" onclick="editJiraTitle()">&#9998; 제목 수정</button></div></div>
        <div style="display:flex;gap:6px;margin-top:6px">
          <button class="btn-jira-unlink" onclick="unlinkJira()">&#128279; 연결 끊기</button>
          <button class="btn-jira-transit" onclick="openTransition()">&#8635; 상태 변경</button>
        </div>
        <div id="dp-jira-transit-wrap" style="display:none;margin-top:10px">
          <div class="transit-panel">
            <div class="transit-panel-lbl">워크플로우 전환</div>
            <select id="dp-jira-transit-sel" class="transit-sel"><option value="">상태 선택...</option></select>
            <div class="transit-actions">
              <button class="btn-transit-apply" onclick="applyTransition()">적용</button>
              <button class="btn-transit-cancel" onclick="closeTransition()">취소</button>
            </div>
          </div>
        </div>
        <div id="dp-jira-action-msg" style="font-size:11px;margin-top:4px;color:var(--tx3)"></div>
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
      <button class="btn-fix" id="btn-fix" onclick="runFixSuggestion(false)">&#128295; 수정 제안</button>
      <button class="dp-regen" id="btn-fix-regen" onclick="runFixSuggestion(true)" style="display:none">&#8635; 재생성</button>
      <div class="ea-result" id="ea-result" style="display:none"></div>
      <div class="ea-result" id="fix-result" style="display:none"></div>
    </div>
    <div id="dp-summary-sec">
      <div class="dp-sec-lbl">메일 요약</div>
      <button class="btn-summary" id="btn-summary" onclick="generateSummary(false)">&#9889; 요약 생성</button>
      <button class="dp-regen" id="btn-summary-regen" onclick="generateSummary(true)" style="display:none">&#8635; 재생성</button>
      <div class="dp-summary-text" id="dp-summary-text" style="display:none"></div>
    </div>
    <div id="dp-draft-sec">
      <div class="dp-sec-lbl">답장 초안</div>
      <button class="btn-draft" id="btn-draft" onclick="generateDraftReply(false)">&#9997; 초안 생성</button>
      <button class="dp-regen" id="btn-draft-regen" onclick="generateDraftReply(true)" style="display:none">&#8635; 재생성</button>
      <div id="dp-draft-wrap" style="display:none">
        <textarea class="dp-draft-area" id="dp-draft-area" spellcheck="false"></textarea>
        <button class="btn-copy-draft" onclick="copyDraft()">&#128203; 클립보드 복사</button>
      </div>
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

<!-- ── NOTIFICATION + CONFIRM DOM ── -->
<div id="notif-wrap"></div>
<div class="cm-ov" id="cm-ov">
  <div class="cm-box" id="cm-box">
    <div class="cm-icon-wrap cm-icon-info" id="cm-icon-wrap"><span id="cm-icon">&#8505;</span></div>
    <div class="cm-title" id="cm-title"></div>
    <div class="cm-msg" id="cm-msg"></div>
    <div id="cm-input-wrap" style="display:none"><input class="cm-input" id="cm-input" type="text" autocomplete="off"></div>
    <div id="cm-list-wrap" style="display:none"><div class="cm-list" id="cm-list"></div></div>
    <div class="cm-btns">
      <button class="cm-btn-cancel" id="cm-cancel" style="display:none">취소</button>
      <button class="cm-btn-ok" id="cm-ok">확인</button>
    </div>
  </div>
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

/* ── THEME ── */
function isDark(){ return document.documentElement.dataset.theme==="dark"; }
const _SVG_MOON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
const _SVG_SUN  = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
function initTheme(){
  const t = localStorage.getItem("dash_theme")||"light";
  document.documentElement.dataset.theme = t;
  const btn = document.getElementById("btn-theme");
  if(btn) btn.innerHTML = t==="dark" ? _SVG_SUN : _SVG_MOON;
}
function toggleTheme(){
  const next = isDark() ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("dash_theme", next);
  const btn = document.getElementById("btn-theme");
  if(btn) btn.innerHTML = next==="dark" ? _SVG_SUN : _SVG_MOON;
  rechartAll();
}
function themeChartColors(){
  return isDark()
    ? {tick:"#7fa0c0",grid:"rgba(255,255,255,.05)",
       bar1bg:"rgba(43,109,255,.7)",bar1bd:"rgba(43,109,255,.95)",
       bar2bg:"rgba(46,202,138,.65)",bar2bd:"rgba(46,202,138,.9)",
       line:"#2b6dff",lineArea:"rgba(43,109,255,.1)",
       donut:["rgba(67,90,120,.75)","rgba(43,109,255,.8)","rgba(46,202,138,.8)"],donutBd:"#0c1830",legend:"#7fa0c0"}
    : {tick:"#a898c4",grid:"rgba(140,118,200,.08)",
       bar1bg:"rgba(124,109,232,.55)",bar1bd:"rgba(124,109,232,.85)",
       bar2bg:"rgba(32,136,120,.55)",bar2bd:"rgba(32,136,120,.85)",
       line:"#7c6de8",lineArea:"rgba(124,109,232,.10)",
       donut:["rgba(128,112,154,.55)","rgba(124,109,232,.70)","rgba(32,136,120,.65)"],donutBd:"#f3f0fd",legend:"#6a5d8a"};
}

let _lastChartPayload = {};  // 차트 재렌더용 데이터 캐시

function rechartAll(){
  const p = _lastChartPayload, c = themeChartColors();
  if(p.mailTeam) renderBarChart("chart-team-mail","empty-team-mail", sortObj(p.mailTeam), c.bar1bg, c.bar1bd);
  if(p.mailMonth) renderLineChart("chart-monthly","empty-monthly", p.mailMonth);
  if(p.jiraStatus) renderDonut("chart-jira-status","empty-jira-status", p.jiraStatus);
  if(p.jiraTeam) renderBarChart("chart-jira-team","empty-jira-team", sortObj(p.jiraTeam), c.bar2bg, c.bar2bd);
}

let _data = [], _manualData = [], _src = "all", _selId = null, _cdwn = 30, _jiraEnabled = false, _jiraAuto = false, _userName = "";
let _sortCol = "received_at", _sortDir = "desc";
let _page = 1;
const _PAGE_SIZE = 20;

// ── SIDEBAR COLLAPSIBLE ──────────────────────────────────────────
function closeMobileSb(){
  const sb = document.getElementById("sidebar");
  const bd = document.getElementById("sb-bd");
  if(sb) sb.classList.remove("sb-mobile-open");
  if(bd) bd.classList.remove("open");
}
function toggleSidebar(){
  const sb  = document.getElementById("sidebar");
  const hdr = document.querySelector(".hdr");
  if(window.innerWidth <= 768){
    const isOpen = sb.classList.toggle("sb-mobile-open");
    let bd = document.getElementById("sb-bd");
    if(!bd){
      bd = document.createElement("div");
      bd.id = "sb-bd"; bd.className = "sb-bd";
      bd.onclick = closeMobileSb;
      document.body.appendChild(bd);
    }
    bd.classList.toggle("open", isOpen);
  } else {
    const collapsed = sb.classList.toggle("collapsed");
    if(hdr) hdr.classList.toggle("sb-collapsed", collapsed);
    localStorage.setItem("sb-collapsed", collapsed ? "1" : "0");
  }
}
window.addEventListener("resize", function(){ if(window.innerWidth > 768) closeMobileSb(); });
(function(){
  if(window.innerWidth > 768 && localStorage.getItem("sb-collapsed") === "1"){
    const sb  = document.getElementById("sidebar");
    const hdr = document.querySelector(".hdr");
    if(sb)  sb.classList.add("collapsed");
    if(hdr) hdr.classList.add("sb-collapsed");
  }
  let _sbTip = null;
  function _getSbTip(){
    if(!_sbTip){
      _sbTip = document.getElementById("sb-tip");
      if(!_sbTip){
        _sbTip = document.createElement("div");
        _sbTip.id = "sb-tip";
        document.body.appendChild(_sbTip);
      }
    }
    return _sbTip;
  }
  document.addEventListener("mouseover", function(e){
    const sb = document.getElementById("sidebar");
    if(!sb || !sb.classList.contains("collapsed")) return;
    const ni = e.target.closest(".nav-item[data-tip]");
    if(!ni) return;
    const t = _getSbTip();
    t.textContent = ni.dataset.tip;
    t.style.display = "block";
    t.style.opacity = "0";
    requestAnimationFrame(function(){
      const r = ni.getBoundingClientRect();
      t.style.left = (r.right + 8) + "px";
      t.style.top = (r.top + r.height / 2 - t.offsetHeight / 2) + "px";
      t.style.opacity = "1";
    });
  });
  document.addEventListener("mouseout", function(e){
    const ni = e.target.closest(".nav-item[data-tip]");
    if(!ni || !_sbTip) return;
    _sbTip.style.opacity = "0";
    setTimeout(function(){ if(_sbTip && _sbTip.style.opacity === "0") _sbTip.style.display = "none"; }, 130);
  });
})();

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
  if(s==="teams")  return '<span class="src src-tm">Teams</span>';
  if(s==="manual") return '<span class="src src-mn">수동</span>';
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

function jiraSt(s){
  if(!s)           return '<span class="jst jst-none">미등록</span>';
  if(s==="진행전") return '<span class="jst jst-todo">진행전</span>';
  if(s==="진행중") return '<span class="jst jst-wip">진행중</span>';
  if(s==="완료")   return '<span class="jst jst-done">완료</span>';
  return '<span class="jst jst-none">'+esc(s)+'</span>';
}

function arBadge(v){
  if(v===true)  return '<span class="ar-y">&#10003; 필요</span>';
  if(v===false) return '<span class="ar-n">불필요</span>';
  return '<span class="pp pp-none">&#8212;</span>';
}

function filtered(){
  const q = (document.getElementById("srch").value||"").toLowerCase();
  const sev = document.getElementById("sev-sel").value;
  const base = _src==="manual" ? _manualData : _data;
  const todayStr = new Date().toLocaleDateString("sv-SE");
  const startVal = (document.getElementById("ds-start")||{}).value || todayStr;
  const endVal   = (document.getElementById("ds-end")||{}).value   || todayStr;
  return base.filter(m => {
    if(_src!=="all" && _src!=="manual" && m.source!==_src) return false;
    if(sev && (m.intent_type||"unknown")!==sev) return false;
    if(q){
      const hay = ((m.subject||"")+" "+(m.sender||"")).toLowerCase();
      if(!hay.includes(q)) return false;
    }
    if(_src==="manual" && m.received_at){
      const d = new Date(m.received_at).toLocaleDateString("sv-SE");
      if(d < startVal || d > endVal) return false;
    }
    return true;
  });
}

function setSidebarFilter(key){
  const sel = document.getElementById("sev-sel");
  sel.value = sel.value===key ? "" : key;
  document.querySelectorAll(".sb-cat").forEach(el=>{
    el.classList.toggle("active", el.dataset.intent===sel.value && sel.value!=="");
  });
  _page = 1;
  const reportVisible = document.getElementById("report-view").style.display !== "none";
  if(reportVisible) showView("today");
  renderTable();
}

function sortBy(col){
  if(_sortCol===col) _sortDir=_sortDir==="desc"?"asc":"desc";
  else{_sortCol=col;_sortDir="desc";}
  _page = 1;
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
    if(_sortCol==="received_at"){
      const av=a.received_at?new Date(a.received_at).getTime():0;
      const bv=b.received_at?new Date(b.received_at).getTime():0;
      return _sortDir==="asc"?av-bv:bv-av;
    }
    const av=String(a[_sortCol]??""), bv=String(b[_sortCol]??"");
    const cmp=av<bv?-1:av>bv?1:0;
    return _sortDir==="asc"?cmp:-cmp;
  });
  const total = rows.length;
  const totalPages = Math.max(1, Math.ceil(total / _PAGE_SIZE));
  if(_page > totalPages) _page = totalPages;
  const pageRows = rows.slice((_page-1)*_PAGE_SIZE, _page*_PAGE_SIZE);
  if(!pageRows.length){
    tb.innerHTML = '<tr><td colspan="11" class="empty">표시할 데이터가 없습니다.</td></tr>';
    renderPager(0, 1);
    return;
  }
  tb.innerHTML = pageRows.map(m => {
    const sel = m.id===_selId ? ' sel' : '';
    const jiraCell = m.jira_key
      ? '<a class="jlnk" href="'+JIRA_BASE+esc(m.jira_key)+'" target="_blank">'+esc(m.jira_key)+'</a>'
        +'<br>'+jiraSt(m.jira_status||null)
      : jiraSt(null);
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
  renderPager(total, totalPages);
}

function renderPager(total, totalPages){
  const el = document.getElementById("pager");
  if(!el) return;
  const from = total ? (_page-1)*_PAGE_SIZE+1 : 0;
  const to   = Math.min(_page*_PAGE_SIZE, total);
  el.innerHTML =
    `<span class="pg-info">${from}–${to} / 총 ${total}건</span>`
    +`<div class="pg-btns">`
    +`<button class="pg-btn" onclick="goPage(1)" ${_page<=1?"disabled":""}>&#171;</button>`
    +`<button class="pg-btn" onclick="goPage(_page-1)" ${_page<=1?"disabled":""}>&#8249;</button>`
    +`<span class="pg-cur">${_page} / ${totalPages}</span>`
    +`<button class="pg-btn" onclick="goPage(_page+1)" ${_page>=totalPages?"disabled":""}>&#8250;</button>`
    +`<button class="pg-btn" onclick="goPage(totalPages)" ${_page>=totalPages?"disabled":""}>&#187;</button>`
    +`</div>`;
}
function goPage(n){ _page = n; renderTable(); }

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
  const curFilter = document.getElementById("sev-sel").value;
  cats.innerHTML = Object.entries(SEV).map(([k,v])=>{
    const n = counts[k]||0;
    const col = n>0?"var(--tx)":"var(--tx3)";
    const act = curFilter===k ? " active" : "";
    return '<div class="sb-cat'+act+'" data-intent="'+k+'" onclick="setSidebarFilter(\\''+k+'\\')"><span class="sb-cat-name">'+v.lbl+'</span><span class="sb-cat-n" style="color:'+col+'">'+n+'</span></div>';
  }).join("");
}

function setSearchLoading(on){
  const bar    = document.getElementById("search-bar");
  const loader = document.getElementById("center-loader");
  const btns   = document.querySelectorAll(".btn-ds-search");
  if(on){
    if(bar)    bar.classList.add("active");
    if(loader) loader.classList.add("active");
    btns.forEach(function(b){ b.disabled = true; });
  } else {
    if(bar)    bar.classList.remove("active");
    if(loader) loader.classList.remove("active");
    btns.forEach(function(b){ b.disabled = false; });
  }
}

async function fetchAndRender(withLoading){
  if(withLoading) setSearchLoading(true);
  try{
    const start = (document.getElementById("ds-start")||{value:""}).value;
    const end   = (document.getElementById("ds-end")||{value:""}).value;
    const todayStr = new Date().toLocaleDateString("sv-SE");
    const firstOfMonth = new Date(); firstOfMonth.setDate(1);
    const fomStr = firstOfMonth.toLocaleDateString("sv-SE");
    const isMonth = start === fomStr && end === todayStr && fomStr !== todayStr;
    const isToday  = !isMonth && (!start || (start === todayStr && end === todayStr));
    const url = isToday
      ? "/dashboard/data"
      : "/dashboard/search?start="+encodeURIComponent(start||todayStr)+"&end="+encodeURIComponent(end||todayStr);
    const res = await fetch(url);
    _data = await res.json();
    _page = 1;
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
    syncJiraStatuses(start && !isToday ? start : null, end && !isToday ? end : null);
  }catch(e){ console.error(e); }
  finally{ if(withLoading) setSearchLoading(false); }
}

async function syncJiraStatuses(start, end){
  try{
    let url = "/dashboard/jira/sync-all";
    if(start && end) url += "?start="+encodeURIComponent(start)+"&end="+encodeURIComponent(end);
    const map = await fetch(url).then(r=>r.json());
    if(!map || !Object.keys(map).length) return;
    let changed = false;
    for(const [id, status] of Object.entries(map)){
      const i = _data.findIndex(m=>m.id===id);
      if(i>=0 && _data[i].jira_status !== status){
        _data[i].jira_status = status;
        changed = true;
      }
      const mi = _manualData.findIndex(m=>m.id===id);
      if(mi>=0 && _manualData[mi].jira_status !== status){
        _manualData[mi].jira_status = status;
        changed = true;
      }
    }
    if(changed) renderTable();
  }catch(e){}
}

// 60초마다 Jira 상태 자동 동기화
setInterval(()=>{ if(document.visibilityState==="visible") syncJiraStatuses(); }, 60000);

function openDetail(id){
  const m = _data.find(x=>x.id===id) || _manualData.find(x=>x.id===id);
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
    lnk.dataset.summary = m.summary || "";
    closeTransition();
    document.getElementById("dp-jira-action-msg").textContent="";
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
  // 요약 섹션 초기화
  document.getElementById("dp-summary-text").style.display = "none";
  document.getElementById("dp-summary-text").textContent = "";
  document.getElementById("btn-summary-regen").style.display = "none";
  const btnSum = document.getElementById("btn-summary");
  btnSum.disabled = false;
  btnSum.innerHTML = "&#9889; 요약 생성";
  // 답장 초안 섹션 초기화
  document.getElementById("dp-draft-wrap").style.display = "none";
  document.getElementById("dp-draft-area").value = "";
  document.getElementById("btn-draft-regen").style.display = "none";
  const btnDraft = document.getElementById("btn-draft");
  btnDraft.disabled = false;
  btnDraft.innerHTML = "&#9997; 초안 생성";
  btnSum.style.display = "";
  btnDraft.style.display = "";
  // 본문 비동기 로딩
  const bodyEl = document.getElementById("dp-body-content");
  bodyEl.textContent = "불러오는 중...";
  fetch("/dashboard/message/"+encodeURIComponent(id))
    .then(r=>r.json())
    .then(d=>{
      bodyEl.textContent = cleanBody(d.body);
      if(d.summary){
        document.getElementById("dp-summary-text").textContent = d.summary;
        document.getElementById("dp-summary-text").style.display = "";
        document.getElementById("btn-summary-regen").style.display = "";
        btnSum.style.display = "none";
      }
      if(d.draft_reply){
        document.getElementById("dp-draft-area").value = d.draft_reply;
        document.getElementById("dp-draft-wrap").style.display = "";
        document.getElementById("btn-draft-regen").style.display = "";
        btnDraft.style.display = "none";
      }
    })
    .catch(()=>{ bodyEl.textContent = "(본문을 불러올 수 없습니다)"; });

  document.getElementById("dp-edit-intent").value = m.intent_type || "unknown";
  document.getElementById("dp-edit-priority").value = m.personal_priority || "";
  document.getElementById("dp-edit-category").value = m.email_category || "";
  document.getElementById("dp-edit-ar").value = m.action_required === true ? "true" : m.action_required === false ? "false" : "";
  document.getElementById("dp-edit-action").value = m.suggested_action || "";
  document.getElementById("dp-save-msg").textContent = "";
  document.getElementById("ea-result").style.display = "none";
  document.getElementById("ea-result").innerHTML = "";
  const btnA = document.getElementById("btn-analyze");
  btnA.disabled = false;
  btnA.innerHTML = "&#128269; AI 오류 분석";
  document.getElementById("fix-result").style.display = "none";
  document.getElementById("fix-result").innerHTML = "";
  const btnF = document.getElementById("btn-fix");
  btnF.disabled = false;
  btnF.innerHTML = "&#128295; 수정 제안";
  // info/spam은 수정 제안 대상이 아니므로 버튼 숨김 (1차 필터)
  btnF.style.display = (m.intent_type === "info" || m.intent_type === "spam") ? "none" : "";
  document.getElementById("btn-fix-regen").style.display = "none";
  document.getElementById("dp-foot").textContent = "조회 시각: "+fmtFull(new Date().toISOString());
  loadSenderHistory(m.sender);
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
    const arRaw = document.getElementById("dp-edit-ar").value;
    const payload = {
      intent_type: document.getElementById("dp-edit-intent").value || "unknown",
      personal_priority: document.getElementById("dp-edit-priority").value || null,
      email_category: document.getElementById("dp-edit-category").value || null,
      suggested_action: document.getElementById("dp-edit-action").value.trim() || null,
      action_required: arRaw === "" ? null : arRaw === "true",
    };
    const res = await fetch("/dashboard/message/"+encodeURIComponent(_selId),{
      method:"PATCH",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload),
    });
    if(res.ok){
      [_data, _manualData].forEach(arr => { const m = arr.find(x=>x.id===_selId); if(m) Object.assign(m, payload); });
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

async function runFixSuggestion(force){
  if(!_selId) return;
  const btn = document.getElementById("btn-fix");
  const regenBtn = document.getElementById("btn-fix-regen");
  const res = document.getElementById("fix-result");
  btn.disabled = true;
  regenBtn.disabled = true;
  btn.textContent = "⏳ 제안 생성 중...";
  res.style.display = "none";
  res.innerHTML = "";
  try{
    const url = "/dashboard/message/"+encodeURIComponent(_selId)+"/fix-suggestion"+(force?"?force=true":"");
    const r = await fetch(url);
    if(!r.ok){ throw new Error(await r.text()); }
    const d = await r.json();
    const s = d.suggestion || {};
    function escNl(t){ return esc(t).replace(/\\n/g,"<br>"); }
    if(s.not_error){
      res.innerHTML = `<div class="ea-card"><div class="ea-card-title">ℹ️ 수정 제안 대상 아님</div><div class="ea-card-body">${escNl(s.reason||"오류·기술 문제 메일이 아니어서 수정 제안을 생성하지 않았습니다.")}</div></div>`;
      res.style.display = "flex";
      regenBtn.style.display = "";
      return;
    }
    let html = "";
    html += `<div class="ea-card">
      <div class="ea-card-title">🩺 진단${d.cached?` <span style="font-weight:400;text-transform:none;letter-spacing:0">(저장된 제안${force?"":" — 재생성 가능"})</span>`:""}</div>
      <div class="ea-card-body">${escNl(s.diagnosis||"—")}</div>
    </div>`;
    if(s.fix_steps && s.fix_steps.length){
      const stepsHtml = s.fix_steps.map((st,i)=>
        `<div class="fix-step"><span class="fix-step-num">${i+1}</span><div><div style="font-size:12px;font-weight:700;color:var(--tx)">${esc(st.title||"조치")}</div><div class="ea-card-body" style="margin-top:2px">${escNl(st.detail||"")}</div></div></div>`
      ).join("");
      html += `<div class="ea-card"><div class="ea-card-title">🔧 단계별 수정 방안</div><div>${stepsHtml}</div></div>`;
    }
    if(s.verification || s.risk){
      html += `<div class="ea-card">
        <div class="ea-card-title">✅ 적용 후 확인</div>
        <div style="display:flex;flex-direction:column;gap:8px">
          ${s.verification?`<div><div style="font-size:10.5px;font-weight:700;color:var(--tx3);margin-bottom:4px">검증 방법</div><div class="ea-card-body">${escNl(s.verification)}</div></div>`:""}
          ${s.risk?`<div${s.verification?` style="border-top:1px solid var(--bd);padding-top:8px"`:""}><div style="font-size:10.5px;font-weight:700;color:var(--tx3);margin-bottom:4px">⚠️ 주의사항</div><div class="ea-card-body">${escNl(s.risk)}</div></div>`:""}
        </div>
      </div>`;
    }
    if(s.reference_note){
      html += `<div class="ea-card"><div class="ea-card-title">📚 유사 사례 참고</div><div class="ea-card-body">${escNl(s.reference_note)}</div></div>`;
    }
    if(d.similar_cases && d.similar_cases.length){
      const casesHtml = d.similar_cases.map(c=>{
        const status = c.jira_status || "미처리";
        const jira = c.jira_key ? ` · ${esc(c.jira_key)}` : "";
        const when = c.received_at ? ` · ${esc(String(c.received_at).slice(0,10))}` : "";
        return `<div style="font-size:12px;color:var(--tx);padding:3px 0">[${esc(status)}] ${esc(c.subject||"(제목 없음)")}${jira}${when}</div>`;
      }).join("");
      html += `<div class="ea-card"><div class="ea-card-title">🗂️ 과거 유사 메일</div><div>${casesHtml}</div></div>`;
    }
    res.innerHTML = html;
    res.style.display = "flex";
    regenBtn.style.display = "";
  }catch(e){
    res.innerHTML = `<div class="ea-card"><div class="ea-card-body" style="color:var(--c-crit)">제안 생성 실패: ${esc(String(e))}</div></div>`;
    res.style.display = "flex";
  }finally{
    btn.disabled = false;
    regenBtn.disabled = false;
    btn.innerHTML = "&#128295; 수정 제안";
  }
}

async function rowDeleteMessage(event, id){
  event.stopPropagation();
  const m = _data.find(x=>x.id===id);
  const label = m ? (m.subject||m.sender||id).slice(0,40) : id;
  if(!await showConfirm("이 메일을 삭제하시겠습니까?\\n\\n"+label,{danger:true,okLabel:"삭제"})) return;
  try{
    const r = await fetch("/dashboard/message/"+encodeURIComponent(id),{method:"DELETE"});
    if(!r.ok){ showNotif("삭제 실패: "+(await r.text()),"err"); return; }
    _data = _data.filter(x=>x.id!==id);
    if(_selId===id) closeDetail();
    else renderTable();
  }catch(e){ showNotif("오류: "+e.message,"err"); }
}

async function deleteMessage(){
  if(!_selId) return;
  const m = _data.find(x=>x.id===_selId);
  const label = m ? (m.subject||m.sender||_selId).slice(0,40) : _selId;
  if(!await showConfirm("이 메일을 삭제하시겠습니까?\\n\\n"+label,{danger:true,okLabel:"삭제"})) return;
  try{
    const r = await fetch("/dashboard/message/"+encodeURIComponent(_selId),{method:"DELETE"});
    if(!r.ok){ showNotif("삭제 실패: "+(await r.text()),"err"); return; }
    _data = _data.filter(x=>x.id!==_selId);
    closeDetail();
  }catch(e){ showNotif("오류: "+e.message,"err"); }
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

async function editJiraTitle(){
  if(!_selId) return;
  const lnk = document.getElementById("dp-jira-lnk");
  const currentTitle = lnk.dataset.summary || "";
  const newTitle = await showPromptInput("새 Jira 제목 수정", "제목 입력...", currentTitle);
  if(!newTitle || newTitle.trim() === currentTitle) return;
  const msgEl = document.getElementById("dp-jira-action-msg");
  msgEl.style.color="var(--tx3)";
  msgEl.textContent="수정 중...";
  try{
    const res = await fetch("/dashboard/jira/"+encodeURIComponent(_selId)+"/title",{
      method:"PATCH",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({summary: newTitle.trim()}),
    });
    const data = await res.json();
    if(res.ok){
      lnk.dataset.summary = newTitle.trim();
      msgEl.style.color="var(--c-ok)";
      msgEl.textContent="✓ 제목이 수정되었습니다.";
    } else {
      msgEl.style.color="var(--c-crit)";
      msgEl.textContent="오류: "+(data.detail||"수정 실패");
    }
  } catch(e){
    msgEl.style.color="var(--c-crit)";
    msgEl.textContent="네트워크 오류: "+e.message;
  }
}

async function unlinkJira(){
  if(!_selId) return;
  const lnk = document.getElementById("dp-jira-lnk");
  const key = lnk.textContent.trim();
  if(!await showConfirm("Jira 티켓 "+key+" 연결을 끊으시겠습니까?\\n(Jira의 티켓은 삭제되지 않습니다.)",{title:"연결 해제",okLabel:"해제"})) return;
  const msgEl = document.getElementById("dp-jira-action-msg");
  msgEl.style.color="var(--tx3)"; msgEl.textContent="처리 중...";
  try{
    const res = await fetch("/dashboard/jira/"+encodeURIComponent(_selId),{method:"DELETE"});
    const data = await res.json();
    if(res.ok){
      const m = _data.find(x=>x.id===_selId);
      if(m) m.jira_key = null;
      document.getElementById("dp-jira-existing").style.display="none";
      document.getElementById("dp-jira-create").style.display="";
      msgEl.textContent="";
      renderTable();
    } else {
      msgEl.style.color="var(--c-crit)";
      msgEl.textContent="오류: "+(data.detail||"실패");
    }
  } catch(e){
    msgEl.style.color="var(--c-crit)"; msgEl.textContent="네트워크 오류";
  }
}

async function openTransition(){
  if(!_selId) return;
  const msgEl = document.getElementById("dp-jira-action-msg");
  const wrap = document.getElementById("dp-jira-transit-wrap");
  const sel = document.getElementById("dp-jira-transit-sel");
  msgEl.style.color="var(--tx3)"; msgEl.textContent="전환 목록 로딩 중...";
  try{
    const res = await fetch("/dashboard/jira/"+encodeURIComponent(_selId)+"/transitions");
    const data = await res.json();
    if(!res.ok){ msgEl.textContent="오류: "+(data.detail||"조회 실패"); return; }
    sel.innerHTML='<option value="">상태 선택...</option>'+data.map(t=>'<option value="'+t.id+'">'+t.name+'</option>').join("");
    wrap.style.display="flex";
    msgEl.textContent="";
  } catch(e){
    msgEl.style.color="var(--c-crit)"; msgEl.textContent="네트워크 오류";
  }
}

function closeTransition(){
  document.getElementById("dp-jira-transit-wrap").style.display="none";
  document.getElementById("dp-jira-transit-sel").innerHTML='<option value="">상태 선택...</option>';
}

async function applyTransition(){
  if(!_selId) return;
  const sel = document.getElementById("dp-jira-transit-sel");
  const tid = sel.value;
  if(!tid) return;
  const tname = sel.options[sel.selectedIndex].text;
  const msgEl = document.getElementById("dp-jira-action-msg");
  msgEl.style.color="var(--tx3)"; msgEl.textContent="상태 변경 중...";
  try{
    const res = await fetch("/dashboard/jira/"+encodeURIComponent(_selId)+"/transitions",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({transition_id:tid}),
    });
    const data = await res.json();
    if(res.ok){
      closeTransition();
      msgEl.style.color="var(--c-ok)";
      msgEl.textContent="\\u2713 '"+tname+"'으로 변경되었습니다.";
      if(data.jira_status){
        // _data 메모리 갱신 (재렌더 시 되돌아가는 문제 방지)
        const di = _data.findIndex(m=>m.id===_selId);
        if(di>=0) _data[di].jira_status = data.jira_status;
        const mi = _manualData.findIndex(m=>m.id===_selId);
        if(mi>=0) _manualData[mi].jira_status = data.jira_status;
        // DOM 즉시 갱신
        const row = document.querySelector("tr[data-id=\\""+_selId+"\\"]");
        if(row){
          const jiraCell = row.querySelector("td:nth-child(10)");
          if(jiraCell){
            const lnk = jiraCell.querySelector("a");
            if(lnk) jiraCell.innerHTML = lnk.outerHTML+"<br>"+jiraSt(data.jira_status);
          }
        }
      }
    } else {
      msgEl.style.color="var(--c-crit)";
      msgEl.textContent="오류: "+(data.detail||"변경 실패");
    }
  } catch(e){
    msgEl.style.color="var(--c-crit)"; msgEl.textContent="네트워크 오류";
  }
}

async function generateSummary(regenerate){
  if(!_selId) return;
  const btn = document.getElementById("btn-summary");
  const regenBtn = document.getElementById("btn-summary-regen");
  const textEl = document.getElementById("dp-summary-text");
  btn.disabled = true;
  regenBtn.disabled = true;
  const origText = regenerate ? regenBtn.innerHTML : btn.innerHTML;
  if(regenerate) regenBtn.innerHTML = "&#9203; 생성 중...";
  else btn.innerHTML = "&#9203; 생성 중...";
  try{
    const url = "/dashboard/message/"+encodeURIComponent(_selId)+"/summarize"+(regenerate?"?regenerate=true":"");
    const r = await fetch(url);
    if(!r.ok) throw new Error(await r.text());
    const d = await r.json();
    textEl.textContent = d.summary || "(요약 없음)";
    textEl.style.display = "";
    btn.style.display = "none";
    regenBtn.style.display = "";
  }catch(e){
    textEl.textContent = "요약 생성 실패: "+e.message;
    textEl.style.display = "";
  }finally{
    btn.disabled = false;
    regenBtn.disabled = false;
    if(regenerate) regenBtn.innerHTML = origText;
    else btn.innerHTML = origText;
  }
}

async function generateDraftReply(regenerate){
  if(!_selId) return;
  const btn = document.getElementById("btn-draft");
  const regenBtn = document.getElementById("btn-draft-regen");
  const wrap = document.getElementById("dp-draft-wrap");
  const area = document.getElementById("dp-draft-area");
  btn.disabled = true;
  regenBtn.disabled = true;
  const origText = regenerate ? regenBtn.innerHTML : btn.innerHTML;
  if(regenerate) regenBtn.innerHTML = "&#9203; 생성 중...";
  else btn.innerHTML = "&#9203; 생성 중...";
  try{
    const url = "/dashboard/message/"+encodeURIComponent(_selId)+"/draft-reply"+(regenerate?"?regenerate=true":"");
    const r = await fetch(url, {method:"POST"});
    if(!r.ok) throw new Error(await r.text());
    const d = await r.json();
    area.value = d.draft || "";
    wrap.style.display = "";
    btn.style.display = "none";
    regenBtn.style.display = "";
  }catch(e){
    area.value = "초안 생성 실패: "+e.message;
    wrap.style.display = "";
  }finally{
    btn.disabled = false;
    regenBtn.disabled = false;
    if(regenerate) regenBtn.innerHTML = origText;
    else btn.innerHTML = origText;
  }
}

function copyDraft(){
  const area = document.getElementById("dp-draft-area");
  navigator.clipboard.writeText(area.value).then(()=>{
    const btn = document.querySelector(".btn-copy-draft");
    const orig = btn.textContent;
    btn.textContent = "✓ 복사됨";
    setTimeout(()=>{ btn.textContent = orig; }, 1500);
  }).catch(()=>{
    area.select();
    document.execCommand("copy");
  });
}

document.getElementById("srch").addEventListener("input", ()=>{ _page=1; renderTable(); });
document.getElementById("sev-sel").addEventListener("change", ()=>{
  const v = document.getElementById("sev-sel").value;
  document.querySelectorAll(".sb-cat").forEach(el=>{
    el.classList.toggle("active", el.dataset.intent===v && v!=="");
  });
  _page = 1;
  renderTable();
});
document.querySelectorAll(".ftab").forEach(t=>{
  t.addEventListener("click", async ()=>{
    document.querySelectorAll(".ftab").forEach(x=>x.classList.remove("active"));
    t.classList.add("active");
    _src = t.dataset.src;
    if(_src==="manual"){
      _manualData = await fetch("/dashboard/direct/messages?source=all").then(r=>r.json()).catch(()=>[]);
    }
    _page = 1;
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

// ── 커스텀 달력 피커 변수 (IIFE보다 먼저 선언) ──────────────────────
let _dpTarget = null;
let _dpPrefix = "";   // "" = 메인바(ds-start/end), "r" = 리포트바(r-start/end)
let _dpYear = 0, _dpMonth = 0;

// 날짜 기본값 = 오늘, pg-sub는 fetchAndRender()가 설정
(function(){
  const today = new Date().toLocaleDateString("sv-SE");
  dsSet("start", today, "");
  dsSet("end",   today, "");
})();

initTheme();
fetchAndRender();
setInterval(fetchAndRender, 30000);
if(location.hash==="#report") showView("report");

// ── 커스텀 달력 피커 함수 ──────────────────────────────────────────

function _dpInpId(w){ return _dpPrefix ? _dpPrefix + "-" + w : "ds-" + w; }
function _dpFldId(w){ return _dpPrefix ? "dpf-" + _dpPrefix + "-" + w : "dpf-" + w; }
function _dpLblId(w){ return _dpPrefix ? "dp-lbl-" + _dpPrefix + "-" + w : "dp-lbl-" + w; }

function dsSet(which, val, px){
  const p = (px !== undefined) ? px : _dpPrefix;
  const inpId = p ? p + "-" + which : "ds-" + which;
  const lblId = p ? "dp-lbl-" + p + "-" + which : "dp-lbl-" + which;
  const inp = document.getElementById(inpId);
  const lbl = document.getElementById(lblId);
  if(inp) inp.value = val;
  if(!lbl) return;
  if(!val){ lbl.textContent = "날짜 선택"; return; }
  const d = new Date(val + "T00:00:00");
  const todayStr = new Date().toLocaleDateString("sv-SE");
  if(val === todayStr) lbl.textContent = "오늘";
  else lbl.textContent = d.toLocaleDateString("ko-KR", {month:"long", day:"numeric"});
}

function dpOpen(which, px){
  _dpPrefix = (px !== undefined) ? px : "";
  _dpTarget = which;
  const inp   = document.getElementById(_dpInpId(which));
  const val   = inp ? inp.value : "";
  const ref   = val ? new Date(val + "T00:00:00") : new Date();
  _dpYear  = ref.getFullYear();
  _dpMonth = ref.getMonth();
  const popup  = document.getElementById("dp-popup");
  const field  = document.getElementById(_dpFldId(which));
  const tgtLbl = document.getElementById("dp-tgt-lbl");
  if(tgtLbl) tgtLbl.textContent = which === "start" ? "시작일 선택" : "종료일 선택";
  document.querySelectorAll(".calpick").forEach(function(f){ f.classList.remove("dp-active"); });
  if(field) field.classList.add("dp-active");
  dpRender();
  popup.classList.add("open");
  if(field){
    const rect = field.getBoundingClientRect();
    const pw = 276, ph = 290;
    let left = rect.left;
    let top  = rect.bottom + 6;
    if(left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
    if(top  + ph > window.innerHeight - 8) top = rect.top - ph - 6;
    popup.style.left = left + "px";
    popup.style.top  = top + "px";
  }
}

function dpClose(){
  const popup = document.getElementById("dp-popup");
  if(popup) popup.classList.remove("open");
  document.querySelectorAll(".calpick").forEach(function(f){ f.classList.remove("dp-active"); });
  _dpTarget = null;
}

function dpMove(dir){
  _dpMonth += dir;
  if(_dpMonth < 0){ _dpMonth = 11; _dpYear--; }
  if(_dpMonth > 11){ _dpMonth = 0; _dpYear++; }
  dpRender();
}

function dpRender(){
  const ttl = document.getElementById("dp-ttl");
  if(ttl) ttl.textContent = _dpYear + "년 " + (_dpMonth + 1) + "월";
  const grid = document.getElementById("dp-grid");
  if(!grid) return;
  const startVal = (document.getElementById(_dpInpId("start")) || {value:""}).value;
  const endVal   = (document.getElementById(_dpInpId("end"))   || {value:""}).value;
  const todayStr = new Date().toLocaleDateString("sv-SE");
  const first    = new Date(_dpYear, _dpMonth, 1);
  const last     = new Date(_dpYear, _dpMonth + 1, 0);
  const startWd  = first.getDay();
  let cells = "";
  for(let i = 0; i < startWd; i++) cells += "<div class='dp-cell empty'></div>";
  for(let d = 1; d <= last.getDate(); d++){
    const mm  = String(_dpMonth + 1).padStart(2, "0");
    const dd  = String(d).padStart(2, "0");
    const ds  = _dpYear + "-" + mm + "-" + dd;
    const wd  = new Date(_dpYear, _dpMonth, d).getDay();
    let cls   = "dp-cell";
    if(wd === 0) cls += " dp-sun";
    if(wd === 6) cls += " dp-sat";
    if(ds === todayStr) cls += " dp-today";
    const isSel   = ds === startVal || ds === endVal;
    const isStart = ds === startVal;
    const isEnd   = ds === endVal;
    const isRange = startVal && endVal && ds > startVal && ds < endVal;
    if(isSel){
      cls += " dp-sel";
      if(isStart && isEnd) cls += " dp-sel-start dp-sel-end";
      else if(isStart)     cls += " dp-sel-start";
      else if(isEnd)       cls += " dp-sel-end";
    }
    if(isRange) cls += " dp-range";
    cells += "<div class='" + cls + "' data-d='" + ds + "' onclick='dpPick(this.dataset.d)'>" + d + "</div>";
  }
  grid.innerHTML = cells;
}

function dpPick(ds){
  if(!_dpTarget) return;
  dsSet(_dpTarget, ds);
  if(_dpTarget === "start"){
    const endVal = (document.getElementById(_dpInpId("end")) || {value:""}).value;
    if(endVal && ds > endVal) dsSet("end", ds);
    const savedPfx = _dpPrefix;
    dpClose();
    dpOpen("end", savedPfx);
    return;
  }
  const startVal = (document.getElementById(_dpInpId("start")) || {value:""}).value;
  if(startVal && ds < startVal){ dsSet("start", ds); dpRender(); return; }
  dpClose();
}

document.addEventListener("click", function(e){
  const popup = document.getElementById("dp-popup");
  if(!popup || !popup.classList.contains("open")) return;
  if(popup.contains(e.target)) return;
  if(e.target.closest && e.target.closest(".calpick")) return;
  dpClose();
});
document.addEventListener("keydown", function(e){
  if(e.key === "Escape") dpClose();
});

// ── 날짜 검색 ──────────────────────────────────────────────
async function runDateSearch(){
  const start = document.getElementById("ds-start").value;
  const end   = document.getElementById("ds-end").value;
  if(!start || !end){ showNotif("시작일과 종료일을 모두 선택하세요.","warn"); return; }
  if(start > end)   { showNotif("시작일이 종료일보다 늦을 수 없습니다.","warn"); return; }
  await fetchAndRender(true);
}

function resetToToday(){
  const today = new Date().toLocaleDateString("sv-SE");
  dsSet("start", today, "");
  dsSet("end",   today, "");
  fetchAndRender(true);
}

function setDsRange(t){
  const today = new Date();
  const ts = today.toLocaleDateString("sv-SE");
  if(t==="week"){
    const mon = new Date(today);
    mon.setDate(mon.getDate() - ((mon.getDay()+6)%7));
    const sun = new Date(mon);
    sun.setDate(mon.getDate() + 6);
    dsSet("start", mon.toLocaleDateString("sv-SE"), "");
    dsSet("end",   sun.toLocaleDateString("sv-SE"), "");
  } else {
    const d = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    const fomStr = d.toLocaleDateString("sv-SE");
    dsSet("start", fomStr,                              "");
    dsSet("end",   lastDay.toLocaleDateString("sv-SE"), "");
    const lbl = document.getElementById("dp-lbl-start");
    if(lbl) lbl.textContent = d.toLocaleDateString("ko-KR", {month:"long", day:"numeric"});
  }
  fetchAndRender(true);
}

async function openSettings(){
  try{
    const res = await fetch("/dashboard/settings");
    if(!res.ok){ showNotif("설정을 불러오지 못했습니다.","err"); return; }
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
  }catch(e){ showNotif("설정 로드 오류: "+e.message,"err"); return; }
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
      const ds = d.deadline_str.replace(/[.]/g,"-");
      if(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(ds)) document.getElementById("st-due-date").value=ds;
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

/* ── 직접 등록 뷰 ── */
let _directTab = "outlook";
let _linkTargetId = null;

function switchDirectTab(tab){
  _directTab = tab;
  document.querySelectorAll(".dtab").forEach(el=>el.classList.toggle("active", el.dataset.dtab===tab));
  loadDirectView(tab);
}

async function loadDirectView(src){
  src = src || _directTab;
  const rows = await fetch("/dashboard/direct/messages?source="+src).then(r=>r.json()).catch(()=>[]);
  const tbody = document.getElementById("direct-tbody");
  if(!rows.length){
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--tx3);padding:32px">항목이 없습니다.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(m=>{
    const jiraCell = m.jira_key
      ? '<a class="jlnk" href="'+(typeof JIRA_BASE!=="undefined"?JIRA_BASE:"")+esc(m.jira_key)+'" target="_blank">'+esc(m.jira_key)+'</a><br>'+jiraSt(m.jira_status||null)
      : jiraSt(null);
    return '<tr>'
      +'<td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(m.subject||"(제목 없음)")+'</td>'
      +'<td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(m.sender||"—")+'</td>'
      +'<td>'+srcBadge(m.source)+'</td>'
      +'<td>'+jiraCell+'</td>'
      +'<td class="t-time">'+fmtDate(m.received_at)+'</td>'
      +'<td><div class="direct-actions">'+buildDirectActions(m)+'</div></td>'
      +'</tr>';
  }).join("");
}

function buildDirectActions(m){
  let btns = "";
  if(!m.jira_key){
    btns += `<button onclick="createDirectJira('${m.id}')">Jira 생성</button>`;
    btns += `<button onclick="openLinkJiraModal('${m.id}')">키 연결</button>`;
  } else {
    btns += `<button onclick="openDirectTransitions('${m.id}')">상태 변경</button>`;
    btns += `<button class="btn-danger" onclick="unlinkDirectJira('${m.id}')">해제</button>`;
  }
  btns += `<button class="btn-danger" onclick="deleteDirectMsg('${m.id}')">삭제</button>`;
  return btns;
}

async function createDirectJira(msgId){
  try{
    const r = await fetch("/dashboard/jira/create/"+msgId,{method:"POST"});
    if(!r.ok) throw new Error((await r.json()).detail||r.status);
    loadDirectView(_directTab);
  }catch(e){ showNotif("Jira 생성 실패: "+e.message,"err"); }
}

function openLinkJiraModal(msgId){
  _linkTargetId = msgId;
  document.getElementById("link-jira-key").value = "";
  document.getElementById("link-jira-modal").classList.add("open");
}
function closeLinkJiraModal(){
  document.getElementById("link-jira-modal").classList.remove("open");
  _linkTargetId = null;
}
async function submitLinkJira(){
  const key = document.getElementById("link-jira-key").value.trim();
  if(!key){ showNotif("Jira 키를 입력하세요.","warn"); return; }
  try{
    const r = await fetch("/dashboard/direct/messages/"+_linkTargetId+"/link",{
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({jira_key: key})
    });
    if(!r.ok) throw new Error((await r.json()).detail||r.status);
    closeLinkJiraModal();
    loadDirectView(_directTab);
  }catch(e){ showNotif("연결 실패: "+e.message,"err"); }
}

async function openDirectTransitions(msgId){
  try{
    const r = await fetch("/dashboard/jira/"+msgId+"/transitions");
    const list = await r.json();                          // API는 배열 반환
    if(!Array.isArray(list)||!list.length){ showNotif("전환 가능한 상태가 없습니다.","warn"); return; }
    const idx = await showSelectList("Jira 상태 전환", list.map(t=>t.name));
    if(idx===null||idx===undefined) return;
    const rr = await fetch("/dashboard/jira/"+msgId+"/transitions",{
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({transition_id: list[idx].id})
    });
    if(!rr.ok) throw new Error((await rr.json()).detail||rr.status);
    loadDirectView(_directTab);
  }catch(e){ showNotif("상태 변경 실패: "+e.message,"err"); }
}

async function unlinkDirectJira(msgId){
  if(!await showConfirm("Jira 키 연결을 해제하시겠습니까?",{title:"연결 해제",okLabel:"해제"})) return;
  try{
    const r = await fetch("/dashboard/jira/"+msgId,{method:"DELETE"});
    if(!r.ok) throw new Error((await r.json()).detail||r.status);
    loadDirectView(_directTab);
  }catch(e){ showNotif("해제 실패: "+e.message,"err"); }
}

async function deleteDirectMsg(msgId){
  if(!await showConfirm("이 항목을 삭제하시겠습니까?",{danger:true,okLabel:"삭제"})) return;
  try{
    const r = await fetch("/dashboard/message/"+msgId,{method:"DELETE"});
    if(!r.ok) throw new Error((await r.json()).detail||r.status);
    loadDirectView(_directTab);
  }catch(e){ showNotif("삭제 실패: "+e.message,"err"); }
}

function openAddDirectModal(){
  document.getElementById("add-src").value = _directTab==="manual" ? "manual" : _directTab==="teams" ? "teams" : "outlook";
  document.getElementById("add-subject").value = "";
  document.getElementById("add-sender").value = "";
  document.getElementById("add-body").value = "";
  document.getElementById("add-direct-modal").classList.add("open");
}
function closeAddDirectModal(){
  document.getElementById("add-direct-modal").classList.remove("open");
}
async function submitAddDirect(){
  const subject = document.getElementById("add-subject").value.trim();
  if(!subject){ showNotif("제목을 입력하세요.","warn"); return; }
  const payload = {
    source:  document.getElementById("add-src").value,
    subject: subject,
    sender:  document.getElementById("add-sender").value.trim(),
    body:    document.getElementById("add-body").value.trim(),
  };
  try{
    const r = await fetch("/dashboard/direct/messages",{
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    if(!r.ok) throw new Error((await r.json()).detail||r.status);
    closeAddDirectModal();
    // 등록 후 수동생성 탭으로 전환하여 결과 확인
    const manualTab = document.querySelector('.ftab[data-src="manual"]');
    if(manualTab){ manualTab.click(); }
    else { fetchAndRender(); }
  }catch(e){ showNotif("등록 실패: "+e.message,"err"); }
}

function gS(){ return document.getElementById("r-start").value; }
function gE(){ return document.getElementById("r-end").value; }

function setRange(t){
  const today = new Date();
  const ts = today.toLocaleDateString("sv-SE");
  if(t==="today"){
    dsSet("start", ts, "r");
    dsSet("end",   ts, "r");
  } else if(t==="week"){
    const mon = new Date(today);
    mon.setDate(mon.getDate() - ((mon.getDay()+6)%7));
    const sun = new Date(mon);
    sun.setDate(mon.getDate() + 6);
    dsSet("start", mon.toLocaleDateString("sv-SE"), "r");
    dsSet("end",   sun.toLocaleDateString("sv-SE"), "r");
  } else {
    const d = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    const fomStr = d.toLocaleDateString("sv-SE");
    dsSet("start", fomStr,                              "r");
    dsSet("end",   lastDay.toLocaleDateString("sv-SE"), "r");
    const lbl = document.getElementById("dp-lbl-r-start");
    if(lbl) lbl.textContent = d.toLocaleDateString("ko-KR", {month:"long", day:"numeric"});
  }
  doSearch(true);
}

function doSearch(withLoading){
  setSearchLoading(withLoading);
  Promise.resolve(loadRptCurrentTab()).finally(function(){ if(withLoading) setSearchLoading(false); });
}
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
    _lastChartPayload.mailTeam = d.by_team||{};
    _lastChartPayload.mailMonth = d.by_month||{};
    renderMailTable(d.list||[]);
    const c = themeChartColors();
    renderBarChart("chart-team-mail","empty-team-mail", sortObj(d.by_team||{}), c.bar1bg, c.bar1bd);
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
    _lastChartPayload.jiraStatus = d.by_status||{};
    _lastChartPayload.jiraTeam = d.by_team||{};
    renderAvgCards(d.avg_days||0, d.total||0, d.by_team||{});
    renderDonut("chart-jira-status","empty-jira-status", d.by_status||{});
    const cj = themeChartColors();
    renderBarChart("chart-jira-team","empty-jira-team", sortObj(d.by_team||{}), cj.bar2bg, cj.bar2bd);
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
  const c = themeChartColors();
  return {responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label(x){return " "+x.raw+unit}}}},
    scales:{x:{ticks:{color:c.tick,font:{size:10}},grid:{color:c.grid}},
            y:{ticks:{color:c.tick,font:{size:10}},grid:{color:c.grid},beginAtZero:true}}};
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
  const c = themeChartColors();
  mkChart(canvasId,{type:"line",data:{labels,datasets:[{data:values,borderColor:c.line,backgroundColor:c.lineArea,fill:true,tension:0.4,pointRadius:4,pointBackgroundColor:c.line}]},options:barOpts("건")});
}

function renderDonut(canvasId, emptyId, byObj){
  const labels=Object.keys(byObj), values=Object.values(byObj);
  const empty = document.getElementById(emptyId);
  if(!values.some(v=>v>0)){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  const c = themeChartColors();
  mkChart(canvasId,{type:"doughnut",data:{labels,datasets:[{data:values,backgroundColor:c.donut,borderColor:c.donutBd,borderWidth:3}]},
    options:{responsive:true,plugins:{legend:{position:"bottom",labels:{color:c.legend,padding:14,font:{size:11}}},tooltip:{callbacks:{label(x){return " "+x.label+": "+x.raw+"건"}}}}}});
}

function sortObj(obj){ const s=Object.entries(obj).sort((a,b)=>b[1]-a[1]); return Object.fromEntries(s); }
function setLoading(tbId, cols){ document.getElementById(tbId).innerHTML='<tr><td colspan="'+cols+'" class="spinner-wrap"><div class="spin"></div></td></tr>'; }

(function(){
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth(), 1);
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  dsSet("start", d.toLocaleDateString("sv-SE"),       "r");
  dsSet("end",   lastDay.toLocaleDateString("sv-SE"), "r");
})();

// ── 발신자 히스토리 ──
async function loadSenderHistory(sender){
  const sec = document.getElementById("dp-sender-hist");
  if(!sender || sender==="-"){ sec.style.display="none"; return; }
  sec.style.display="";
  document.getElementById("sh-stats-wrap").style.display="none";
  document.getElementById("sh-list").innerHTML="";
  document.getElementById("sh-loading").textContent="불러오는 중...";
  try{
    const r = await fetch("/dashboard/sender/"+encodeURIComponent(sender)+"/history");
    if(!r.ok){ document.getElementById("sh-loading").textContent=""; return; }
    const data = await r.json();
    renderSenderHistory(data, sender);
  }catch(e){
    document.getElementById("sh-loading").textContent="";
  }
}

function renderSenderHistory(data, currentSender){
  const stats   = (data && data.stats)   || {};
  const msgs    = (data && data.messages) || [];
  const loading = document.getElementById("sh-loading");
  const statsWrap = document.getElementById("sh-stats-wrap");
  const listEl  = document.getElementById("sh-list");
  if(!loading || !statsWrap || !listEl) return;
  loading.textContent = "";
  document.getElementById("sh-total").textContent  = (stats.total !== undefined)         ? stats.total         : 0;
  document.getElementById("sh-urgent").textContent = (stats.urgent_count !== undefined)  ? stats.urgent_count  : 0;
  document.getElementById("sh-avg").textContent    = (stats.avg_hours !== null && stats.avg_hours !== undefined) ? stats.avg_hours+"h" : "-";
  statsWrap.style.display = "";
  const prev = msgs.filter(function(m){ return m.id !== _selId; });
  if(!prev.length){
    listEl.innerHTML = '<div class="sh-none">이 발신자로부터의 이전 이력이 없습니다.</div>';
    return;
  }
  var rows = prev.map(function(m){
    var jiraCell = m.jira_key
      ? '<span style="color:var(--acc);font-size:10px;font-weight:700">'+esc(m.jira_key)+'</span>'
      : '<span style="color:var(--tx3);font-size:10px">-</span>';
    return '<tr style="cursor:pointer" onclick="shOpenDetail(this)" data-id="'+esc(m.id)+'" title="상세 보기">'
      +'<td class="sh-subj">'+esc(m.subject||"(제목 없음)")+'</td>'
      +'<td>'+sevBadge(m.intent_type||"unknown")+'</td>'
      +'<td style="white-space:nowrap;font-size:11px;color:var(--tx3)">'+fmtDate(m.received_at)+'</td>'
      +'<td>'+jiraCell+'</td>'
      +'</tr>';
  }).join("");
  listEl.innerHTML =
    '<table class="sh-table"><thead><tr>'
    +'<th>제목</th><th>분류</th><th>수신일</th><th>Jira</th>'
    +'</tr></thead><tbody>'+rows+'</tbody></table>';
}

function shOpenDetail(row){
  var id = row.dataset.id;
  if(!id) return;
  var m = _data.find(function(x){ return x.id===id; })
       || _manualData.find(function(x){ return x.id===id; });
  if(!m){ showNotif("이 메시지는 현재 날짜 범위에 없습니다. 날짜를 조정 후 검색해 주세요.", "warn"); return; }
  openDetail(id);
}

// ── 자연어 AI 검색 ──
let _nlActive = false;
let _nlQuery  = null;

function toggleNLSearch(){
  if(_nlActive){ clearNLSearch(); return; }
  showPromptInput("AI 자연어 검색", "예: 지난달 서버 긴급 이슈, Jira 없는 작업요청").then(function(q){
    if(q && q.trim()) runNLSearch(q.trim());
  });
}

async function runNLSearch(query){
  const bar    = document.getElementById("search-bar");
  const loader = document.getElementById("center-loader");
  if(bar)    bar.classList.add("active");
  if(loader) loader.classList.add("active");
  try{
    const res = await fetch("/dashboard/nl-search",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({query:query})
    });
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail||res.status);
    _nlActive = true;
    _nlQuery  = query;
    _data     = data.messages;
    _page     = 1;
    renderTable();
    const f = data.parsed_filter || {};
    const parts = [];
    if(f.date_from || f.date_to) parts.push("📅 "+(f.date_from||"")+"~"+(f.date_to||""));
    if(f.intent_types && f.intent_types.length) parts.push("🏷 "+f.intent_types.join(","));
    if(f.keywords    && f.keywords.length)    parts.push("🔍 "+f.keywords.join(" & "));
    if(f.has_jira === true)  parts.push("Jira등록");
    if(f.has_jira === false) parts.push("Jira미등록");
    if(f.personal_priority) parts.push("중요도:"+f.personal_priority);
    const condStr = parts.length ? "  |  "+parts.join("  ·  ") : "";
    document.getElementById("nl-badge-text").textContent = "AI: "+query+condStr;
    document.getElementById("nl-badge").classList.add("visible");
    document.getElementById("btn-nl-search").classList.add("active");
    if(data.llm_used === false){
      showNotif("AI 엔진 미연결 — 키워드 검색으로 "+data.messages.length+"건 표시", "warn", 3500);
    } else {
      showNotif("AI 검색 완료 — "+data.messages.length+"건  "+condStr.replace(/\s*\|\s*/,"").trim(), "ok", 3000);
    }
  }catch(e){
    showNotif("AI 검색 실패: "+e.message, "err");
  }finally{
    if(bar)    bar.classList.remove("active");
    if(loader) loader.classList.remove("active");
  }
}

function clearNLSearch(){
  _nlActive = false;
  _nlQuery  = null;
  document.getElementById("nl-badge").classList.remove("visible");
  document.getElementById("btn-nl-search").classList.remove("active");
  fetchAndRender();
}

// ── CUSTOM ALERT / CONFIRM / PROMPT / SELECT SYSTEM ──
let _cmResolve = null;
const _notifTitles = {err:"오류", ok:"성공", warn:"주의", info:"알림"};
const _notifIcons  = {err:"✕",   ok:"✓",   warn:"!",   info:"i"};

function showNotif(msg, type, dur){
  type = type||"info"; dur = dur||3500;
  const wrap = document.getElementById("notif-wrap");
  const el = document.createElement("div");
  el.className = "notif-item n-"+type;
  el.innerHTML =
    '<div class="notif-icon">'+(_notifIcons[type]||"i")+'</div>'
    +'<div class="notif-body"><div class="notif-title">'+(_notifTitles[type]||type)+'</div>'
    +'<div class="notif-msg">'+esc(msg)+'</div></div>'
    +'<button class="notif-close" onclick="this.closest(\\'.notif-item\\').remove()">&#10005;</button>'
    +'<div class="notif-progress" style="animation-duration:'+dur+'ms"></div>';
  wrap.prepend(el);
  setTimeout(function(){
    el.classList.add("leaving");
    el.addEventListener("animationend", function(){ el.remove(); }, {once:true});
  }, dur);
}

function _cmOpen(opts){
  const ov  = document.getElementById("cm-ov");
  const iw  = document.getElementById("cm-icon-wrap");
  iw.className = "cm-icon-wrap "+(opts.iconCls||"cm-icon-info");
  document.getElementById("cm-icon").textContent  = opts.icon||"i";
  document.getElementById("cm-title").textContent = opts.title||"알림";
  document.getElementById("cm-msg").textContent   = opts.msg||"";
  const okBtn = document.getElementById("cm-ok");
  okBtn.textContent = opts.okLabel||"확인";
  okBtn.className   = "cm-btn-ok"+(opts.danger?" danger":"");
  okBtn.dataset.val = "";
  const cancelBtn = document.getElementById("cm-cancel");
  cancelBtn.style.display = opts.showCancel ? "" : "none";
  cancelBtn.textContent   = opts.cancelLabel||"취소";
  const inw = document.getElementById("cm-input-wrap");
  const lw  = document.getElementById("cm-list-wrap");
  inw.style.display = opts.showInput ? "" : "none";
  lw.style.display  = opts.showList  ? "" : "none";
  if(opts.showInput){
    const inp = document.getElementById("cm-input");
    inp.placeholder = opts.placeholder||"";
    inp.value = opts.defaultVal||"";
    setTimeout(function(){ inp.focus(); }, 60);
  }
  if(opts.showList){
    const list = document.getElementById("cm-list");
    list.innerHTML = (opts.items||[]).map(function(item, i){
      return '<div class="cm-list-item" data-idx="'+i+'" onclick="document.querySelectorAll(\\'.cm-list-item\\').forEach(function(x){x.classList.remove(\\'cm-selected\\')});this.classList.add(\\'cm-selected\\');document.getElementById(\\'cm-ok\\').dataset.val=\\''+i+'\\'">'+ esc(String(item))+'</div>';
    }).join("");
  }
  ov.classList.add("open");
}

function _cmClose(val){
  document.getElementById("cm-ov").classList.remove("open");
  if(_cmResolve){ var r=_cmResolve; _cmResolve=null; r(val); }
}

document.getElementById("cm-ok").addEventListener("click", function(){
  if(document.getElementById("cm-input-wrap").style.display!=="none"){
    _cmClose(document.getElementById("cm-input").value.trim()||null);
  } else if(document.getElementById("cm-list-wrap").style.display!=="none"){
    var v=document.getElementById("cm-ok").dataset.val;
    _cmClose(v===""?null:parseInt(v,10));
  } else {
    _cmClose(true);
  }
});
document.getElementById("cm-cancel").addEventListener("click", function(){ _cmClose(null); });
document.getElementById("cm-ov").addEventListener("click", function(e){ if(e.target.id==="cm-ov") _cmClose(null); });
document.getElementById("cm-input").addEventListener("keydown", function(e){
  if(e.key==="Enter")  _cmClose(document.getElementById("cm-input").value.trim()||null);
  if(e.key==="Escape") _cmClose(null);
});

function showConfirm(msg, opts){
  opts = opts||{};
  return new Promise(function(r){
    _cmResolve = r;
    _cmOpen({
      icon:       opts.icon||(opts.danger?"\\uD83D\\uDDD1":"\\u26A0\\uFE0F"),
      iconCls:    opts.danger ? "cm-icon-del" : "cm-icon-warn",
      title:      opts.title||(opts.danger?"삭제 확인":"확인"),
      msg:        msg,
      okLabel:    opts.okLabel||"확인",
      cancelLabel:opts.cancelLabel||"취소",
      danger:     opts.danger,
      showCancel: true,
    });
  });
}

function showAlert(msg, type){
  type = type||"info";
  return new Promise(function(r){
    _cmResolve = function(){ r(); };
    var clsMap = {err:"cm-icon-err", ok:"cm-icon-ok", warn:"cm-icon-warn", info:"cm-icon-info"};
    var iconMap = {err:"\\u2715", ok:"\\u2713", warn:"\\u26A0\\uFE0F", info:"\\u2139"};
    _cmOpen({
      icon:    iconMap[type]||"\\u2139",
      iconCls: clsMap[type]||"cm-icon-info",
      title:   _notifTitles[type]||"알림",
      msg:     msg,
      okLabel: "확인",
      showCancel: false,
    });
  });
}

function showPromptInput(title, placeholder, defaultVal){
  return new Promise(function(r){
    _cmResolve = r;
    _cmOpen({
      icon:"\\u270F\\uFE0F", iconCls:"cm-icon-info",
      title:title, msg:"",
      okLabel:"확인", cancelLabel:"취소",
      showCancel:true, showInput:true,
      placeholder:placeholder, defaultVal:defaultVal||"",
    });
  });
}

function showSelectList(title, items){
  return new Promise(function(r){
    _cmResolve = r;
    _cmOpen({
      icon:"\\uD83D\\uDD04", iconCls:"cm-icon-info",
      title:title, msg:"",
      okLabel:"선택", cancelLabel:"취소",
      showCancel:true, showList:true, items:items,
    });
  });
}

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
    action_required: bool | None = None


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


class JiraTitlePatch(BaseModel):
    summary: str


class JiraTransitionPayload(BaseModel):
    transition_id: str


class DirectMessagePayload(BaseModel):
    source: str = "outlook"
    subject: str
    sender: str = ""
    body: str = ""


class LinkJiraPayload(BaseModel):
    jira_key: str


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
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%237c6de8'/><stop offset='1' stop-color='%23a78bfa'/></linearGradient></defs><rect width='32' height='32' rx='7' fill='url(%23g)'/><text x='16' y='22' font-family='system-ui,sans-serif' font-size='16' font-weight='900' fill='white' text-anchor='middle'>M</text></svg>">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#faf8ff;--bg-s:#f3f0fd;--bg-e:#ede8fb;--bg-card:#f6f3fe;--bg-hov:#e6e0f8;--bd:rgba(140,118,200,.14);--bd2:rgba(140,118,200,.26);--bd-acc:rgba(110,85,220,.40);--tx:#2c2450;--tx2:#6a5d8a;--tx3:#a898c4;--acc:#7c6de8;--acc-dim:rgba(124,109,232,.12);--c-crit:#d04060;--c-ok:#208878;--c-med:#a07828}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{min-height:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--tx);font-size:13px}
a{color:inherit;text-decoration:none}button{font-family:inherit;cursor:pointer}
.hdr{height:58px;background:var(--bg-s);border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;padding:0 24px;position:sticky;top:0;z-index:100}
.hdr-l{display:flex;align-items:center;gap:14px}
.back-btn{display:flex;align-items:center;justify-content:center;width:32px;height:32px;border:1px solid var(--bd2);border-radius:7px;color:var(--tx2);font-size:18px;background:transparent;transition:all .12s;flex-shrink:0}
.back-btn:hover{background:var(--bg-hov);color:var(--tx)}
.logo{width:43px;height:34px;background:linear-gradient(135deg,#7c6de8,#a78bfa);border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:9px;color:#fff;letter-spacing:.1em;flex-shrink:0;box-shadow:0 2px 12px rgba(124,109,232,.35)}
.hdr-titles{display:flex;flex-direction:column}
.hdr-co{font-size:10px;font-weight:700;color:var(--tx3);letter-spacing:.09em;text-transform:uppercase}
.hdr-sys{font-size:13.5px;font-weight:700;letter-spacing:-.02em}
.clock{font-size:12px;color:var(--tx2);font-variant-numeric:tabular-nums;font-weight:500}
.rpt-page{padding:20px 28px;max-width:1360px;margin:0 auto}
.gf-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px;background:var(--bg-card);border:1px solid var(--bd);border-left:3px solid var(--acc);border-radius:10px;padding:10px 16px}
.gf-lbl{font-size:10px;font-weight:800;color:var(--tx3);letter-spacing:.09em;text-transform:uppercase;flex-shrink:0}
.ds-date{background:var(--bg-e);border:1px solid var(--bd);border-radius:7px;padding:6px 10px;color:var(--tx);font-size:12.5px;outline:none;font-family:inherit;transition:border-color .15s;min-width:128px}
.ds-date:focus{border-color:var(--bd-acc)}
.ds-sep{color:var(--tx3);font-size:12px}
.btn-ds-search{background:var(--acc);color:#fff;border:none;border-radius:7px;padding:6px 14px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap}
.rng-presets{display:flex;gap:2px;margin-left:4px;padding-left:8px;border-left:1px solid var(--bd)}
.rng-btn{background:transparent;border:1px solid var(--bd);border-radius:6px;padding:4px 10px;font-size:11.5px;font-weight:600;color:var(--tx2);cursor:pointer;transition:all .12s;white-space:nowrap;font-family:inherit}
.rng-btn:hover{background:var(--acc-dim);border-color:var(--acc);color:var(--acc)}
.btn{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:7px;font-size:12px;font-weight:600;border:none;transition:all .12s}
.btn-ghost{background:transparent;color:var(--tx2);border:1px solid var(--bd2)}
.btn-ghost:hover{background:var(--bg-e);color:var(--tx)}
.rtabs{display:flex;gap:2px;margin-bottom:16px;background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:4px}
.rtab{flex:1;padding:8px 10px;border:none;background:transparent;color:var(--tx2);font-size:12px;font-weight:600;border-radius:7px;cursor:pointer;transition:all .12s;white-space:nowrap}
.rtab.active{background:var(--bg-s);color:var(--tx);box-shadow:0 1px 4px rgba(140,118,200,.18)}
.rtab:hover:not(.active){color:var(--tx)}
.sum-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.sum-card{background:var(--bg-card);border:1px solid var(--bd);border-radius:10px;padding:16px 18px;position:relative;overflow:hidden}
.sum-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2.5px;border-radius:10px 10px 0 0;background:var(--acc)}
.sum-card-warn::before{background:var(--c-crit)}
.sum-lbl{font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.06em;text-transform:uppercase;margin-bottom:8px}
.sum-val{font-size:28px;font-weight:900;letter-spacing:-.04em;line-height:1;color:var(--tx)}
.sum-card-warn .sum-val{color:var(--c-crit)}
.sum-desc{font-size:10.5px;color:var(--tx3);margin-top:4px}
.unproc-banner{background:linear-gradient(135deg,rgba(208,64,96,.06),rgba(124,109,232,.06));border:1px dashed rgba(208,64,96,.22);border-radius:10px;padding:13px 18px;display:flex;align-items:center;gap:12px;cursor:pointer;transition:background .12s}
.unproc-banner:hover{background:linear-gradient(135deg,rgba(208,64,96,.10),rgba(124,109,232,.10))}
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
thead th{padding:9px 13px;text-align:left;font-size:10.5px;font-weight:700;color:var(--tx3);letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--bd);background:var(--bg-s);white-space:nowrap;position:sticky;top:0;z-index:2;box-shadow:0 1px 0 var(--bd)}
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
.jbadge-yes{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(32,136,120,.10);color:var(--c-ok)}
.jbadge-no{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:rgba(208,64,96,.10);color:var(--c-crit)}
.jlnk{color:var(--acc);font-size:11px;font-weight:600}
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
.modal-ov{position:fixed;inset:0;background:rgba(80,60,140,.30);z-index:200;opacity:0;pointer-events:none;transition:opacity .2s}
.modal-ov.open{opacity:1;pointer-events:all}
.md-panel{position:fixed;right:0;top:0;bottom:0;width:440px;background:var(--bg-s);border-left:3px solid var(--acc);box-shadow:-8px 0 36px rgba(80,60,140,.18);z-index:305;transform:translateX(100%);transition:transform .22s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden}
.md-panel.open{transform:translateX(0)}
.md-hdr{padding:16px 20px;border-bottom:1px solid var(--bd2);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:10px}
.md-hdr-title{font-size:13.5px;font-weight:700;color:var(--tx);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.md-hdr button{background:rgba(124,109,232,.08);border:none;color:var(--tx2);font-size:15px;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.md-body{flex:1;overflow-y:auto;padding:18px 20px;display:flex;flex-direction:column;gap:10px}
.dp-field{background:rgba(124,109,232,.05);border:1px solid var(--bd);border-radius:8px;padding:9px 11px}
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
html[data-theme="dark"]{--bg:#080f1c;--bg-s:#0b1527;--bg-e:#0e1d38;--bg-card:#0c1830;--bg-hov:#132040;--bd:rgba(255,255,255,.06);--bd2:rgba(255,255,255,.10);--bd-acc:rgba(50,120,255,.35);--tx:#dde6f4;--tx2:#7fa0c0;--tx3:#435a78;--acc:#2b6dff;--acc-dim:rgba(43,109,255,.13);--c-crit:#ff4444;--c-ok:#2eca8a;--c-med:#ffb820}
html[data-theme="dark"] .logo{background:linear-gradient(135deg,#1a3a8f,#2b6dff)}
html[data-theme="dark"] .dp-field{background:rgba(43,109,255,.07)}
html[data-theme="dark"] .jlnk{color:#5b9ef7}
html[data-theme="dark"] .avg-card{background:var(--bg-card);border-color:var(--bd)}
html[data-theme="dark"] .t-tag,.html[data-theme="dark"] .r-tab{border-color:var(--bd)}
html[data-theme="dark"] .r-tab.active{background:var(--acc-dim);border-color:var(--acc);color:var(--acc)}
html[data-theme="dark"] .btn-ds-search{background:#2b6dff}

/* ── RESPONSIVE ── */
@media (max-width:768px){
  .sum-cards{grid-template-columns:repeat(2,1fr)}
  .chart-row{grid-template-columns:1fr}
  .md-panel{width:100vw}
  .gf-bar{flex-wrap:wrap;gap:6px}
  .rng-presets{flex-wrap:wrap;gap:4px}
  .rtabs{flex-wrap:wrap}
  .rtab{font-size:11px;padding:6px 8px}
  .hist-filter{gap:6px}
  .srch{min-width:120px}
  .hdr{padding:0 12px 0 0}
  .clock,.last-upd{display:none}
}
@media (max-width:480px){
  .sum-cards{grid-template-columns:1fr 1fr}
  .rtab{font-size:10.5px;padding:5px 6px}
  .rpt-page{padding:14px 12px}
}
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
  <div class="hdr-r" style="display:flex;align-items:center;gap:10px">
    <span class="clock" id="clock">--:--:--</span>
    <button class="btn btn-ghost" id="btn-theme" onclick="toggleTheme()" title="테마 변경" style="padding:5px 8px;display:inline-flex;align-items:center;justify-content:center;width:32px;height:28px"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></button>
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
    <div class="rng-presets">
      <button class="rng-btn" onclick="setRange('today')">오늘</button>
      <button class="rng-btn" onclick="setRange('week')">이번 주</button>
      <button class="rng-btn" onclick="setRange('month')">이번 달</button>
    </div>
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

function isDark(){ return document.documentElement.dataset.theme==="dark"; }
const _SVG_MOON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
const _SVG_SUN  = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
function initTheme(){
  const t = localStorage.getItem("dash_theme")||"light";
  document.documentElement.dataset.theme = t;
  const btn = document.getElementById("btn-theme");
  if(btn) btn.innerHTML = t==="dark" ? _SVG_SUN : _SVG_MOON;
}
function toggleTheme(){
  const next = isDark() ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("dash_theme", next);
  const btn = document.getElementById("btn-theme");
  if(btn) btn.innerHTML = next==="dark" ? _SVG_SUN : _SVG_MOON;
  rechartAll();
}
function themeChartColors(){
  return isDark()
    ? {tick:"#7fa0c0",grid:"rgba(255,255,255,.05)",
       bar1bg:"rgba(43,109,255,.7)",bar1bd:"rgba(43,109,255,.95)",
       bar2bg:"rgba(46,202,138,.65)",bar2bd:"rgba(46,202,138,.9)",
       line:"#2b6dff",lineArea:"rgba(43,109,255,.1)",
       donut:["rgba(67,90,120,.75)","rgba(43,109,255,.8)","rgba(46,202,138,.8)"],donutBd:"#0c1830",legend:"#7fa0c0"}
    : {tick:"#a898c4",grid:"rgba(140,118,200,.08)",
       bar1bg:"rgba(124,109,232,.55)",bar1bd:"rgba(124,109,232,.85)",
       bar2bg:"rgba(32,136,120,.55)",bar2bd:"rgba(32,136,120,.85)",
       line:"#7c6de8",lineArea:"rgba(124,109,232,.10)",
       donut:["rgba(128,112,154,.55)","rgba(124,109,232,.70)","rgba(32,136,120,.65)"],donutBd:"#f3f0fd",legend:"#6a5d8a"};
}
let _lastChartPayload = {};
function rechartAll(){
  const p = _lastChartPayload, c = themeChartColors();
  if(p.mailTeam) renderBarChart("chart-team-mail","empty-team-mail", sortObj(p.mailTeam), c.bar1bg, c.bar1bd);
  if(p.mailMonth) renderLineChart("chart-monthly","empty-monthly", p.mailMonth);
  if(p.jiraStatus) renderDonut("chart-jira-status","empty-jira-status", p.jiraStatus);
  if(p.jiraTeam) renderBarChart("chart-jira-team","empty-jira-team", sortObj(p.jiraTeam), c.bar2bg, c.bar2bd);
}

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
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth(), 1);
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  document.getElementById("r-start").value = d.toLocaleDateString("sv-SE");
  document.getElementById("r-end").value = lastDay.toLocaleDateString("sv-SE");
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
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    document.getElementById("r-start").value = d.toLocaleDateString("sv-SE");
    document.getElementById("r-end").value = lastDay.toLocaleDateString("sv-SE");
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
    _lastChartPayload.mailTeam = d.by_team||{};
    _lastChartPayload.mailMonth = d.by_month||{};
    renderMailTable(d.list||[]);
    const c = themeChartColors();
    renderBarChart("chart-team-mail","empty-team-mail", sortObj(d.by_team||{}), c.bar1bg, c.bar1bd);
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
    _lastChartPayload.jiraStatus = d.by_status||{};
    _lastChartPayload.jiraTeam = d.by_team||{};
    renderAvgCards(d.avg_days||0, d.total||0, d.by_team||{});
    renderDonut("chart-jira-status","empty-jira-status", d.by_status||{});
    const cj = themeChartColors();
    renderBarChart("chart-jira-team","empty-jira-team", sortObj(d.by_team||{}), cj.bar2bg, cj.bar2bd);
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
  const c = themeChartColors();
  return {responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label(x){return " "+x.raw+unit}}}},
    scales:{x:{ticks:{color:c.tick,font:{size:10}},grid:{color:c.grid}},
            y:{ticks:{color:c.tick,font:{size:10}},grid:{color:c.grid},beginAtZero:true}}};
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
  const c = themeChartColors();
  mkChart(canvasId,{type:"line",data:{labels,datasets:[{data:values,borderColor:c.line,backgroundColor:c.lineArea,fill:true,tension:0.4,pointRadius:4,pointBackgroundColor:c.line}]},options:barOpts("건")});
}

function renderDonut(canvasId, emptyId, byObj){
  const labels=Object.keys(byObj), values=Object.values(byObj);
  const empty = document.getElementById(emptyId);
  if(!values.some(v=>v>0)){ document.getElementById(canvasId).style.display="none"; empty.style.display=""; return; }
  document.getElementById(canvasId).style.display=""; empty.style.display="none";
  const c = themeChartColors();
  mkChart(canvasId,{type:"doughnut",data:{labels,datasets:[{data:values,backgroundColor:c.donut,borderColor:c.donutBd,borderWidth:3}]},
    options:{responsive:true,plugins:{legend:{position:"bottom",labels:{color:c.legend,padding:14,font:{size:11}}},tooltip:{callbacks:{label(x){return " "+x.label+": "+x.raw+"건"}}}}}});
}

function sortObj(obj){ const s=Object.entries(obj).sort((a,b)=>b[1]-a[1]); return Object.fromEntries(s); }
function setLoading(tbId, cols){ document.getElementById(tbId).innerHTML='<tr><td colspan="'+cols+'" class="spinner-wrap"><div class="spin"></div></td></tr>'; }
function esc(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

initTheme();
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

    @app.get("/dashboard/direct/messages")
    async def get_direct_messages(source: str = "all"):
        return pipeline._store.get_manual_messages(source if source != "all" else None)

    @app.post("/dashboard/direct/messages")
    async def create_direct_message(payload: DirectMessagePayload):
        try:
            src = MessageSource(payload.source.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 source: {payload.source}")
        msg_id = _uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        pipeline._store.mark_processed(
            message_id=msg_id,
            source=src.value,
            sender=payload.sender or None,
            subject=payload.subject,
            received_at=now.isoformat(),
            body=payload.body or None,
            is_manual=True,
        )
        return {"id": msg_id}

    @app.post("/dashboard/direct/messages/{message_id}/link")
    async def link_jira_to_direct(message_id: str, payload: LinkJiraPayload):
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        key = payload.jira_key.strip().upper()
        pipeline._store.update_jira_key(message_id, key)
        pipeline._store.update_jira_status(message_id, "진행전")
        return {"jira_key": key, "jira_status": "진행전"}

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
        return {
            "body": row.get("body") or "",
            "summary": row.get("summary") or "",
            "draft_reply": row.get("draft_reply") or "",
        }

    @app.get("/dashboard/message/{message_id}/summarize")
    async def summarize_message(message_id: str, regenerate: bool = False):
        import ollama as _ollama
        from inbound_gw_agent.handlers.ticket_handler import _SUMMARIZE_SYSTEM
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        if row.get("summary") and not regenerate:
            return {"summary": row["summary"]}
        msg = _row_to_msg(row)
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"본문:\n{msg.body[:2000]}"
        )
        try:
            ollama_client = _ollama.AsyncClient(host=settings.ollama_base_url)
            response = await ollama_client.chat(
                model=settings.ollama_model,
                messages=[
                    {"role": "system", "content": _SUMMARIZE_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
            )
            summary = response.message.content.strip()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM 오류: {exc}") from exc
        pipeline._store.update_summary(message_id, summary)
        return {"summary": summary}

    @app.post("/dashboard/message/{message_id}/draft-reply")
    async def draft_reply_message(message_id: str, regenerate: bool = False):
        import ollama as _ollama
        from inbound_gw_agent.handlers.ticket_handler import _DRAFT_REPLY_SYSTEM
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        if row.get("draft_reply") and not regenerate:
            return {"draft": row["draft_reply"]}
        msg = _row_to_msg(row)
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"본문:\n{msg.body[:2000]}"
        )
        try:
            user_display_name = settings.user_name or "담당자"
            system_prompt = _DRAFT_REPLY_SYSTEM.replace("[USER_NAME]", user_display_name)
            ollama_client = _ollama.AsyncClient(host=settings.ollama_base_url)
            response = await ollama_client.chat(
                model=settings.ollama_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            draft = response.message.content.strip()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM 오류: {exc}") from exc
        pipeline._store.update_draft_reply(message_id, draft)
        return {"draft": draft}

    @app.patch("/dashboard/message/{message_id}")
    async def patch_message_meta(message_id: str, payload: MessageMetaPatch):
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        ar = ("1" if payload.action_required else "0") if payload.action_required is not None else None
        pipeline._store._conn.execute(
            "UPDATE processed_messages SET intent_type=?, personal_priority=?, email_category=?, suggested_action=?, action_required=? WHERE id=?",
            (payload.intent_type, payload.personal_priority, payload.email_category, payload.suggested_action, ar, message_id),
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

    @app.get("/dashboard/message/{message_id}/fix-suggestion")
    async def get_fix_suggestion(message_id: str, force: bool = False):
        import json as _json
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")

        # 1차 필터: 정보성/스팸 메일은 LLM 호출 없이 비대상 처리
        if row.get("intent_type") in ("info", "spam"):
            return {
                "suggestion": {
                    "not_error": True,
                    "reason": "정보성/스팸 메일로 분류되어 수정 제안 대상이 아닙니다.",
                },
                "similar_cases": [],
                "cached": False,
            }

        # 캐시: 이미 생성된 제안이 있으면 재사용 (force=true면 재생성, 실패 결과는 캐시 무시)
        if not force and row.get("fix_suggestion"):
            try:
                cached = _json.loads(row["fix_suggestion"])
                if not cached.get("suggestion", {}).get("error"):
                    return {**cached, "cached": True}
            except (ValueError, TypeError):
                pass  # 캐시 손상 시 재생성

        msg = _row_to_msg(row)
        similar_cases = pipeline._store.find_similar_cases(
            message_id=message_id,
            subject=row.get("subject"),
            body=row.get("body"),
        )

        from inbound_gw_agent.handlers.fix_suggester import suggest_fix
        suggestion = await suggest_fix(msg, similar_cases)

        result = {
            "suggestion": suggestion,
            "similar_cases": [
                {
                    "subject": c.get("subject"),
                    "received_at": c.get("received_at"),
                    "jira_key": c.get("jira_key"),
                    "jira_status": c.get("jira_status"),
                }
                for c in similar_cases
            ],
        }
        # LLM 실패 결과는 캐시하지 않는다 — 다음 클릭 시 재시도되도록
        if not suggestion.get("error"):
            pipeline._store.update_fix_suggestion(message_id, _json.dumps(result, ensure_ascii=False))
        return {**result, "cached": False}

    @app.delete("/dashboard/message/{message_id}")
    async def delete_message(message_id: str):
        deleted = pipeline._store.delete_message(message_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        return {"status": "ok"}

    @app.get("/dashboard/sender/{sender}/history")
    async def get_sender_history(sender: str):
        return pipeline._store.get_sender_history(sender)

    @app.post("/dashboard/nl-search")
    async def nl_search(request: Request):
        import re as _re
        import json as _json
        import ollama as _ollama
        from datetime import timedelta, timezone as _tz
        body = await request.json()
        query_text = str(body.get("query", "")).strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="query 필드가 필요합니다.")
        _KST = _tz(timedelta(hours=9))
        settings = get_settings()
        today_kst = datetime.now(_KST)
        month_start = today_kst.replace(day=1).strftime("%Y-%m-%d")
        prev_month_last = today_kst.replace(day=1) - timedelta(days=1)
        prev_month_first = prev_month_last.replace(day=1)
        week_monday = today_kst - timedelta(days=today_kst.weekday())
        week_end = today_kst.strftime("%Y-%m-%d")
        prompt = (
            "당신은 이메일 검색 필터 추출기입니다. 사용자 쿼리를 분석해 JSON만 반환하세요. 설명 없이 JSON만 출력하세요.\n\n"
            "[규칙]\n"
            "- keywords: 제목·본문에서 찾을 내용 단어(2자 이상). 날짜·분류 표현은 keywords에 넣지 마세요.\n"
            "- intent_types: urgent(긴급)/task(작업요청)/inquiry(문의)/project(프로젝트)/info(공지)/spam(스팸)/unknown\n"
            "- 해당 없는 필드는 null\n\n"
            f"[날짜 기준]\n"
            f"오늘: {today_kst.strftime('%Y-%m-%d')}\n"
            f"이번달: {month_start} ~ {week_end}\n"
            f"지난달: {prev_month_first.strftime('%Y-%m-%d')} ~ {prev_month_last.strftime('%Y-%m-%d')}\n"
            f"이번주: {week_monday.strftime('%Y-%m-%d')} ~ {week_end}\n\n"
            "[예시]\n"
            'Q: "지난달 서버 장애" -> {"date_from":"'+prev_month_first.strftime("%Y-%m-%d")+'","date_to":"'+prev_month_last.strftime("%Y-%m-%d")+'","intent_types":["urgent"],"keywords":["서버","장애"],"has_jira":null,"personal_priority":null}\n'
            'Q: "Jira 없는 작업 요청" -> {"date_from":null,"date_to":null,"intent_types":["task"],"keywords":null,"has_jira":false,"personal_priority":null}\n'
            'Q: "이번주 그룹웨어 오류" -> {"date_from":"'+week_monday.strftime("%Y-%m-%d")+'","date_to":"'+week_end+'","intent_types":null,"keywords":["그룹웨어","오류"],"has_jira":null,"personal_priority":null}\n\n'
            f'쿼리: "{query_text}"\n'
            "JSON:"
        )
        import asyncio as _asyncio
        _STRUCT_WORDS = {"이번달","지난달","이번주","오늘","긴급","작업","요청","관련","있는","없는","메일","전체","문의","공지","스팸"}
        llm_used = True
        filters: dict = {}
        try:
            client = _ollama.AsyncClient(host=settings.ollama_base_url)
            response = await _asyncio.wait_for(
                client.chat(
                    model=settings.ollama_model,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=30.0,
            )
            raw = response.message.content
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            if not m:
                raise ValueError("JSON not found")
            filters = _json.loads(m.group())
        except Exception as exc:
            log.warning("nl_search_llm_failed", error=str(exc))
            llm_used = False

        # 키워드 보강: LLM이 뽑지 않았거나 LLM 실패 시 쿼리 단어에서 추출
        if not filters.get("keywords"):
            words = [w for w in _re.split(r"[\s,]+", query_text) if len(w) > 1 and w not in _STRUCT_WORDS]
            if words:
                filters["keywords"] = words

        # Hard filter: 날짜/분류/Jira 여부만 SQL WHERE에 사용
        candidates = pipeline._store.nl_search(
            date_from=filters.get("date_from"),
            date_to=filters.get("date_to"),
            intent_types=filters.get("intent_types"),
            keywords=None,
            has_jira=filters.get("has_jira"),
            personal_priority=filters.get("personal_priority"),
        )

        # Soft scoring: 키워드 일치 수로 관련성 계산
        kws = [k.lower() for k in (filters.get("keywords") or []) if k]
        if kws:
            def _score(msg: dict) -> int:
                text = " ".join(filter(None, [
                    msg.get("subject") or "", msg.get("sender") or "", msg.get("body") or "",
                ])).lower()
                return sum(1 for kw in kws if kw in text)
            scored = [(_score(m), m) for m in candidates]
            messages = [m for s, m in sorted(scored, key=lambda x: (-x[0], 0)) if s > 0]
        else:
            messages = candidates

        return {"messages": messages, "parsed_filter": filters, "llm_used": llm_used}


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
        pipeline._store.update_jira_status(message_id, "진행전")
        log.info("jira_created_manually", message_id=message_id[:8], jira_key=jira_key)
        return {"status": "created", "jira_key": jira_key}

    @app.patch("/dashboard/jira/{message_id}/title")
    async def update_jira_title(message_id: str, payload: JiraTitlePatch):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        jira_key = row.get("jira_key")
        if not jira_key:
            raise HTTPException(status_code=404, detail="연결된 Jira 티켓이 없습니다.")
        if not payload.summary.strip():
            raise HTTPException(status_code=400, detail="제목은 비워둘 수 없습니다.")
        try:
            handler = JiraTicketHandler()
            await handler.update_issue_summary(jira_key, payload.summary.strip())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Jira 오류: {exc}") from exc
        return {"status": "updated", "jira_key": jira_key}

    @app.get("/dashboard/jira/sync-all")
    async def sync_all_jira_statuses(start: str | None = None, end: str | None = None):
        """Jira에서 현재 상태를 조회하여 DB를 일괄 동기화한다."""
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        if start and end:
            messages = pipeline._store.get_messages_by_date_range(start, end)
        else:
            messages = pipeline._store.get_today_messages()
        targets = [m for m in messages if m.get("jira_key")]
        if not targets:
            return {}
        handler = JiraTicketHandler()
        result: dict[str, str] = {}
        for m in targets:
            try:
                status = await handler.get_issue_status(m["jira_key"])
                pipeline._store.update_jira_status(m["id"], status)
                result[m["id"]] = status
            except Exception:
                pass
        return result  # {message_id: jira_status}

    @app.delete("/dashboard/jira/{message_id}")
    async def unlink_jira(message_id: str):
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        if not row.get("jira_key"):
            raise HTTPException(status_code=404, detail="연결된 Jira 티켓이 없습니다.")
        pipeline._store.clear_jira_key(message_id)
        log.info("jira_unlinked", message_id=message_id[:8])
        return {"status": "unlinked"}

    @app.get("/dashboard/jira/{message_id}/transitions")
    async def get_jira_transitions(message_id: str):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        jira_key = row.get("jira_key")
        if not jira_key:
            raise HTTPException(status_code=404, detail="연결된 Jira 티켓이 없습니다.")
        try:
            handler = JiraTicketHandler()
            return await handler.get_transitions(jira_key)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Jira 오류: {exc}") from exc

    @app.get("/dashboard/jira/{message_id}/status")
    async def refresh_jira_status(message_id: str):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        row = pipeline._store.get_message_by_id(message_id)
        if not row or not row.get("jira_key"):
            raise HTTPException(status_code=404, detail="연결된 Jira 티켓이 없습니다.")
        try:
            handler = JiraTicketHandler()
            new_status = await handler.get_issue_status(row["jira_key"])
            pipeline._store.update_jira_status(message_id, new_status)
            return {"status": new_status}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Jira 오류: {exc}") from exc

    @app.post("/dashboard/jira/{message_id}/transitions")
    async def apply_jira_transition(message_id: str, payload: JiraTransitionPayload):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        jira_key = row.get("jira_key")
        if not jira_key:
            raise HTTPException(status_code=404, detail="연결된 Jira 티켓이 없습니다.")
        if not payload.transition_id.strip():
            raise HTTPException(status_code=400, detail="transition_id가 필요합니다.")
        try:
            handler = JiraTicketHandler()
            await handler.apply_transition(jira_key, payload.transition_id.strip())
            new_status = await handler.get_issue_status(jira_key)
            pipeline._store.update_jira_status(message_id, new_status)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Jira 오류: {exc}") from exc
        return {"status": "transitioned", "jira_key": jira_key, "jira_status": new_status}

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
        pipeline._store.update_jira_status(message_id, "진행전")
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
            " COALESCE(received_at,processed_at) AS received_at, processed_at, jira_done_at"
            " FROM processed_messages"
            " WHERE COALESCE(received_at,processed_at) >= ? AND COALESCE(received_at,processed_at) < ?"
            " ORDER BY COALESCE(received_at,processed_at) DESC",
            (s_iso, e_iso),
        ).fetchall()
        result = []
        for id_, sender, subject, intent_type, jira_key, received_at, processed_at, jira_done_at in rows:
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
            if jira_key:
                end_ts = jira_done_at or processed_at
                if end_ts:
                    try:
                        ra = _dt.fromisoformat(received_at or processed_at)
                        pa = _dt.fromisoformat(end_ts)
                        m = int((pa - ra).total_seconds() / 60)
                        if m >= 0:
                            if m < 60:
                                proc_str = f"{m}분"
                            elif m < 1440:
                                proc_str = f"{m // 60}시간 {m % 60}분"
                            else:
                                proc_str = f"{m // 1440}일 {(m % 1440) // 60}시간"
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
        msg_id = generate_message_id(payload.sender, received_at, payload.subject)

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
