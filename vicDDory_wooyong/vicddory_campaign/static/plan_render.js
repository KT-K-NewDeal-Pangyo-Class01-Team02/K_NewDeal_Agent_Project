// 빅또리출동! 기획안 마크다운 → 문서(HTML). 점장 화면(campaign.js)과 지사 승인 화면(hq.js)이 같이 쓴다.
// 모든 글자를 먼저 이스케이프한 뒤 굵게 · 코드 · 목록 · 표만 태그로 바꾼다.
(function () {
  const esc = (t) => t.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());

  function markdownToHtml(md) {
    const lines = md.replace(/\r/g, '').split('\n');
    const out = [];
    const stack = [];  // 열린 목록 [{ kind, indent }] — 들여쓰기로 하위 목록을 만든다
    const closeOne = () => { const top = stack.pop(); out.push(`</li></${top.kind}>`); };
    const closeAll = () => { while (stack.length) closeOne(); };
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      const t = line.trim();
      if (!t) continue;  // 빈 줄은 목록을 끊지 않는다 (번호가 1부터 다시 시작하지 않게)
      if (/^\|.*\|$/.test(t) && lines[i + 1] && /^\|?\s*:?-{2,}/.test(lines[i + 1].trim())) {
        closeAll();
        const head = cells(t);
        const rows = [];
        i += 2;
        while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) { rows.push(cells(lines[i])); i += 1; }
        i -= 1;
        out.push('<div class="plan-table-wrap"><table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') +
          '</tr></thead><tbody>' + rows.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>');
        continue;
      }
      const h = t.match(/^(#{1,6})\s+(.*)$/);
      if (h) { closeAll(); const lv = Math.min(4, Math.max(2, h[1].length - 1)); out.push(`<h${lv}>${inline(h[2])}</h${lv}>`); continue; }
      const m = line.match(/^(\s*)(?:([-*])|(\d+)[.)])\s+(.*)$/);
      if (m) {
        const indent = m[1].replace(/\t/g, '  ').length;
        const kind = m[2] ? 'ul' : 'ol';
        while (stack.length && stack[stack.length - 1].indent > indent) closeOne();
        const top = stack[stack.length - 1];
        if (top && top.indent === indent) {
          if (top.kind !== kind) { closeOne(); out.push(`<${kind}>`); stack.push({ kind, indent }); } else out.push('</li>');
        } else { out.push(`<${kind}>`); stack.push({ kind, indent }); }
        out.push(`<li>${inline(m[4])}`);
        continue;
      }
      if (/^-{3,}$/.test(t)) { closeAll(); continue; }
      if (stack.length && /^\s{2,}/.test(line)) { out.push(`<br>${inline(t)}`); continue; }  // 목록 항목의 이어지는 줄
      closeAll();
      out.push(`<p>${inline(t)}</p>`);
    }
    closeAll();
    return out.join('');
  }

  window.vicPlan = { esc, toHtml: markdownToHtml };
})();
