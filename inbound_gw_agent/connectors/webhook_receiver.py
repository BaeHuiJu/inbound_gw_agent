from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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
.logo{width:34px;height:34px;background:linear-gradient(135deg,#1a4fff,#0ea5e9);border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:13px;color:#fff;letter-spacing:-.5px;flex-shrink:0;box-shadow:0 2px 12px rgba(43,109,255,.4)}
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
.btn-story{padding:7px 14px;background:transparent;color:var(--c-fix);border:1px solid rgba(168,85,247,.35);border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;margin-top:7px;display:block}
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

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:2px}
::-webkit-scrollbar-thumb:hover{background:var(--tx3)}
</style>
</head>
<body>

<header class="hdr">
  <div class="hdr-l">
    <div class="logo">MI</div>
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
      <div class="nav-item active">
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
      <div class="nav-item" style="opacity:.45;pointer-events:none">
        <svg class="nav-ico" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
          <path d="M5 7h6M5 10h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        리포트
        <span class="nav-soon">준비중</span>
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
    <div class="main-in">

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
            <thead>
              <tr>
                <th>ID</th>
                <th>출처</th>
                <th>제목</th>
                <th>발신자</th>
                <th>분류</th>
                <th>중요도</th>
                <th>카테고리</th>
                <th>액션</th>
                <th>수신 시각</th>
                <th>Jira</th>
              </tr>
            </thead>
            <tbody id="tbody"><tr><td colspan="10" class="empty">데이터를 불러오는 중...</td></tr></tbody>
          </table>
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
          <input id="st-md" class="st-input st-md-input" type="number" min="0.5" step="0.5" value="1">
          <span style="font-size:12px;color:var(--tx2)">M/D</span>
        </div>
      </div>
      <div>
        <div class="st-preview-title">&#49373;&#49457;&#46112; &#49828;&#53664;&#47532; &#51228;&#47785;</div>
        <div class="st-preview-box" id="st-preview-title-box">&#8212;</div>
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
        <button class="btn-jira" id="btn-create-jira" onclick="createJiraManually()">&#127931; Jira 티켓 생성</button>
        <div id="dp-jira-msg" style="font-size:11px;margin-top:6px;color:var(--tx3)"></div>
      </div>
      <button class="btn-story" id="btn-create-story" onclick="openStoryModal()" style="display:none">&#128221; 스토리 작성</button>
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
          <div class="af-step"><div class="step-ic ic-pend">3</div><span class="lbl-pend">원인 분석 (준비 중)</span></div>
          <div class="af-step"><div class="step-ic ic-pend">4</div><span class="lbl-pend">자동 수정 실행 (준비 중)</span></div>
          <div class="af-step"><div class="step-ic ic-pend">5</div><span class="lbl-pend">수정 결과 검증 (준비 중)</span></div>
        </div>
        <div class="af-prog"><div class="af-fill" id="dp-prog" style="width:40%"></div></div>
      </div>
    </div>
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

function renderTable(){
  const tb = document.getElementById("tbody");
  const rows = filtered();
  if(!rows.length){
    tb.innerHTML = '<tr><td colspan="10" class="empty">표시할 데이터가 없습니다.</td></tr>';
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
    const res = await fetch("/dashboard/data");
    _data = await res.json();
    updateStats(_data);
    renderTable();
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

  document.getElementById("dp-foot").textContent = "조회 시각: "+fmtFull(new Date().toISOString());
  document.getElementById("ov").classList.add("open");
  document.getElementById("dp").classList.add("open");
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

// today label
const _td = new Date();
document.getElementById("pg-sub").textContent =
  _td.toLocaleDateString("ko-KR",{year:"numeric",month:"long",day:"numeric",weekday:"long"})+" 기준 | 실시간 오류 인바운드 현황";

fetchAndRender();
setInterval(fetchAndRender, 30000);

async function openSettings(){
  try{
    const res = await fetch("/dashboard/settings");
    if(!res.ok){ alert("설정을 불러오지 못했습니다."); return; }
    const d = await res.json();
    document.getElementById("cfg-name").value = d.user_name || "";
    document.getElementById("cfg-email").value = d.user_email || "";
    document.getElementById("cfg-keywords").value = d.user_keywords || "";
    document.getElementById("cfg-jira-auto").checked = !!d.jira_auto_create;
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
async function saveSettings(){
  const btn = document.getElementById("cfg-save");
  const msg = document.getElementById("cfg-msg");
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
      })
    });
    const d = await res.json();
    if(res.ok){
      _jiraAuto = document.getElementById("cfg-jira-auto").checked;
      msg.style.color = "var(--c-ok)";
      msg.textContent = "저장됐습니다. 다음 메일부터 새 설정이 적용됩니다.";
    } else {
      msg.style.color = "var(--c-crit)";
      msg.textContent = "오류: "+(d.detail||"저장 실패");
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
  document.getElementById("st-preview-title-box").textContent = "["+team+"] "+task+" ("+md+" M/D)";
}

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
  const team = document.getElementById("st-team").value.trim();
  const task = document.getElementById("st-task").value.trim();
  const md = parseFloat(document.getElementById("st-md").value||"1") || 1;
  try{
    const res = await fetch("/dashboard/jira/story/create/"+encodeURIComponent(_storyMsgId),{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({md, team, task_summary: task})
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


class PersonalSettingsPayload(BaseModel):
    user_name: str = ""
    user_email: str = ""
    user_keywords: str = ""
    jira_auto_create: bool = False


class StoryCreatePayload(BaseModel):
    md: float
    team: str = ""
    task_summary: str = ""


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


def create_app(pipeline: "Pipeline") -> FastAPI:
    app = FastAPI(title="Inbound GW Agent", docs_url=None, redoc_url=None)
    settings = get_settings()

    @app.get("/")
    async def root():
        return {"status": "ok", "endpoints": {"webhook": "POST /webhook/message", "health": "GET /health", "dashboard": "GET /dashboard"}}

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        return _DASHBOARD_HTML

    @app.get("/dashboard/data")
    async def dashboard_data():
        return pipeline._store.get_today_messages()

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
        }

    @app.post("/dashboard/settings")
    async def update_personal_settings(payload: PersonalSettingsPayload):
        env_path = Path(".env")
        updates = {
            "USER_NAME": payload.user_name,
            "USER_EMAIL": payload.user_email,
            "USER_KEYWORDS": payload.user_keywords,
            "JIRA_AUTO_CREATE": "true" if payload.jira_auto_create else "false",
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

    @app.post("/dashboard/jira/story/create/{message_id}")
    async def create_story(message_id: str, payload: StoryCreatePayload):
        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler

        if not settings.jira_enabled:
            raise HTTPException(status_code=400, detail="Jira가 비활성화 상태입니다. .env에서 JIRA_ENABLED=true로 설정하세요.")
        row = pipeline._store.get_message_by_id(message_id)
        if not row:
            raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다.")
        msg = _row_to_msg(row)
        try:
            handler = JiraTicketHandler()
            jira_key = await handler.create_story(msg, payload.md, payload.team, payload.task_summary)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Jira 연결 오류: {exc}") from exc
        if not jira_key:
            raise HTTPException(status_code=500, detail="Jira 스토리 생성에 실패했습니다.")
        pipeline._store.update_jira_key(message_id, jira_key)
        log.info("jira_story_created_manually", message_id=message_id[:8], jira_key=jira_key)
        return {"status": "created", "jira_key": jira_key}

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
        if settings.webhook_secret:
            if x_webhook_secret != settings.webhook_secret:
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
