from pathlib import Path
import json

root = Path('.')

webapp_path = root / 'app/api/webapp.py'
webapp = webapp_path.read_text(encoding='utf-8')
old_rank = '''    for index, row in enumerate(table_rows, start=1):
        if row["name"] == current_user.display_name:
            current_rank = index
            current_points = row["points"]
            break
'''
new_rank = '''    for index, row in enumerate(table_rows, start=1):
        # build_table_rows already exposes the stable User.id. Matching by id
        # avoids a null/wrong rank when a display name changes or is duplicated.
        if row.get("user_id") == current_user.id:
            current_rank = index
            current_points = row["points"]
            break
'''
if old_rank not in webapp:
    raise SystemExit('Cannot find dashboard rank lookup')
webapp_path.write_text(webapp.replace(old_rank, new_rank, 1), encoding='utf-8')

css_path = root / 'app/miniapp_frontend/src/styles.css'
css = css_path.read_text(encoding='utf-8')
marker = '/* Native replacements for retired runtime UI patches (v3.9.16) */'
if marker in css:
    raise SystemExit('Final native CSS marker already present')
css += r'''

/* Native replacements for retired runtime UI patches (v3.9.16) */
/* Keep the quick-prediction hero compact without mutating the DOM at runtime. */
.next-match-hero {
  padding: 11px;
  border-radius: 20px;
}
.next-match-hero-top {
  margin-bottom: 8px;
  gap: 8px;
}
.next-match-kicker { font-size: 12px; }
.next-match-countdown {
  padding: 4px 8px;
  font-size: 11px;
}
.next-match-teams {
  margin-bottom: 8px;
  gap: 6px;
}
.next-match-team { gap: 4px; }
.next-match-team strong { font-size: 13px; }
.next-match-team .flag:not(.club-mark) {
  width: 44px;
  height: 32px;
}
.next-match-team .club-mark {
  width: 66px;
  height: 66px;
  border-radius: 14px;
}
.next-match-team .club-mark > .club-mark-logo { padding: 6px; }
.next-match-team .club-mark-country {
  bottom: -7px;
  width: 24px;
  height: 20px;
}
.next-match-versus { gap: 3px; }
.next-match-versus b { font-size: 20px; }
.next-match-versus small { font-size: 10px; }
.next-match-status {
  min-height: 34px;
  margin-bottom: 8px;
  padding: 6px 9px;
  border-radius: 12px;
  gap: 6px;
}
.next-match-status > span {
  width: 18px;
  height: 18px;
}
.next-match-status strong { font-size: 12.5px; }
.next-match-status small {
  font-size: 10px;
  padding-left: 24px;
}
.next-match-cta {
  min-height: 40px;
  height: 40px;
  border-radius: 13px;
  font-size: 13px;
}

/* The UCL league-phase table should fit a phone viewport, as the previous
   v3.9.7 patch did, but now through ordinary component CSS. */
.ucl-league-phase-panel { padding: 10px; }
.ucl-table-scroll {
  width: 100%;
  overflow: hidden;
}
.ucl-phase-table {
  width: 100%;
  min-width: 0;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 10px;
}
.ucl-phase-table th,
.ucl-phase-table td {
  padding: 6px 2px;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ucl-phase-table th:nth-child(1),
.ucl-phase-table td:nth-child(1) { width: 24px; }
.ucl-phase-table th:nth-child(2),
.ucl-phase-table td:nth-child(2) { width: 128px; text-align: left; }
.ucl-phase-table th:nth-child(3),
.ucl-phase-table td:nth-child(3),
.ucl-phase-table th:nth-child(4),
.ucl-phase-table td:nth-child(4),
.ucl-phase-table th:nth-child(5),
.ucl-phase-table td:nth-child(5),
.ucl-phase-table th:nth-child(6),
.ucl-phase-table td:nth-child(6) { width: 22px; }
.ucl-phase-table th:nth-child(7),
.ucl-phase-table td:nth-child(7) { width: 34px; }
.ucl-phase-table th:nth-child(8),
.ucl-phase-table td:nth-child(8),
.ucl-phase-table th:nth-child(9),
.ucl-phase-table td:nth-child(9) { width: 24px; }
.ucl-table-club {
  width: 100%;
  gap: 4px;
  overflow: hidden;
}
.ucl-table-club .club-mark.mini {
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  border-radius: 6px;
}
.ucl-table-club .club-mark.mini > .club-mark-logo { padding: 2px; }
.ucl-table-club strong {
  min-width: 0;
  display: block;
  color: #f4f7ff;
  font-size: 10px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ucl-phase-table tbody tr.ucl-direct { background: rgba(22,211,145,.035); }
.ucl-phase-table tbody tr.ucl-playoff { background: rgba(255,191,53,.025); }
.ucl-phase-table tbody tr.ucl-out { opacity: .74; }
.ucl-phase-table tbody tr.ucl-direct td:first-child {
  border-left: 4px solid #16d391;
  background: rgba(22,211,145,.08);
}
.ucl-phase-table tbody tr.ucl-playoff td:first-child {
  border-left: 4px solid #ffbf35;
  background: rgba(255,191,53,.08);
}
.ucl-phase-table tbody tr.ucl-out td:first-child {
  border-left: 4px solid #657089;
  background: rgba(101,112,137,.08);
}

@media (max-width: 390px) {
  .next-match-hero { padding: 10px; }
  .next-match-team .club-mark {
    width: 58px;
    height: 58px;
  }
  .ucl-phase-table th:nth-child(2),
  .ucl-phase-table td:nth-child(2) { width: 108px; }
  .ucl-table-club strong { font-size: 9.5px; }
}
'''
css_path.write_text(css, encoding='utf-8')

package_path = root / 'app/miniapp_frontend/package.json'
package = json.loads(package_path.read_text(encoding='utf-8'))
if package.get('version') != '3.9.15':
    raise SystemExit(f"Unexpected package version: {package.get('version')}")
package['version'] = '3.9.16'
package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

lock_path = root / 'app/miniapp_frontend/package-lock.json'
lock = json.loads(lock_path.read_text(encoding='utf-8'))
lock['version'] = '3.9.16'
if '' in lock.get('packages', {}):
    lock['packages']['']['version'] = '3.9.16'
lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
