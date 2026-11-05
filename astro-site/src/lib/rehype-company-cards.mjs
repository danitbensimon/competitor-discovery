// Tag markdown tables whose first header is "Company" so the blog can render
// each row as a card, and give every cell its column name as data-label.
const text = (n) => (n.type === 'text' ? n.value : (n.children || []).map(text).join(''));
const els = (n, tag) => (n.children || []).filter((c) => c.type === 'element' && (!tag || c.tagName === tag));

function walk(node) {
  if (node.type === 'element' && node.tagName === 'table') {
    const thead = els(node, 'thead')[0];
    const heads = thead ? els(els(thead, 'tr')[0] || {}, 'th').map((th) => text(th).trim()) : [];
    if (heads[0] === 'Company') {
      node.properties = { ...node.properties, className: ['co-table'] };
      for (const tbody of els(node, 'tbody')) {
        for (const tr of els(tbody, 'tr')) {
          els(tr, 'td').forEach((td, i) => { td.properties = { ...td.properties, dataLabel: heads[i] || '' }; });
        }
      }
    }
  }
  (node.children || []).forEach(walk);
}

export default function rehypeCompanyCards() {
  return (tree) => walk(tree);
}
