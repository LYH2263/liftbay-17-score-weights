import { useEffect, useState } from "react";
import { api } from "../api/client";
type B = {
  id: number; name: string; floors: number;
  same_dir_bonus: number; idle_bonus: number; distance_weight: number;
};
type Weights = { same_dir_bonus: number; idle_bonus: number; distance_weight: number };

const DEFAULT_WEIGHTS: Weights = { same_dir_bonus: 40, idle_bonus: 20, distance_weight: 5 };
const WEIGHT_FIELDS: { key: keyof Weights; label: string; hint: string }[] = [
  { key: "same_dir_bonus", label: "同向加分", hint: "与呼梯同向且未越过时" },
  { key: "idle_bonus", label: "空闲加分", hint: "轿厢空闲时" },
  { key: "distance_weight", label: "距离权重", hint: "每楼层距离扣分" },
];

export default function BuildingsPage() {
  const [rows, setRows] = useState<B[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Weights>>({});
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  useEffect(() => {
    api<B[]>("/buildings").then(bs => {
      setRows(bs);
      setDrafts(Object.fromEntries(bs.map(b => [b.id, {
        same_dir_bonus: b.same_dir_bonus, idle_bonus: b.idle_bonus, distance_weight: b.distance_weight,
      }])));
    });
  }, []);
  function setWeight(id: number, key: keyof Weights, raw: string) {
    const v = Number(raw);
    setDrafts(d => ({ ...d, [id]: { ...d[id]!, [key]: Number.isFinite(v) ? v : 0 } }));
  }
  async function save(b: B) {
    setMsg(""); setErr("");
    const w = drafts[b.id]!;
    if ([w.same_dir_bonus, w.idle_bonus, w.distance_weight].some(v => !Number.isFinite(v) || v < 0)) {
      setErr(`「${b.name}」权重需为不小于 0 的数字`);
      return;
    }
    try {
      const saved = await api<B>(`/buildings/${b.id}`, { method: "PATCH", body: JSON.stringify(w) });
      setRows(rs => rs.map(r => r.id === saved.id ? saved : r));
      setMsg(`「${b.name}」权重已保存：同向 ${saved.same_dir_bonus} / 空闲 ${saved.idle_bonus} / 距离 ${saved.distance_weight}`);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  function resetRow(b: B) {
    setDrafts(d => ({ ...d, [b.id]: { ...DEFAULT_WEIGHTS } }));
  }
  return (<>
    <h2>楼栋</h2>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    <table className="table">
      <thead><tr>
        <th>名称</th><th>楼层数</th><th>同向加分</th><th>空闲加分</th><th>距离权重</th><th></th>
      </tr></thead>
      <tbody>{rows.map(b => {
        const w = drafts[b.id];
        return (
          <tr key={b.id}>
            <td>{b.name}</td>
            <td className="mono">{b.floors}</td>
            {WEIGHT_FIELDS.map(f => (
              <td key={f.key} title={f.hint}>
                <input
                  type="number" min={0} step={0.5} style={{ width: 92 }}
                  value={w ? w[f.key] : ""}
                  onChange={e => setWeight(b.id, f.key, e.target.value)}
                  aria-label={`${b.name} ${f.label}`}
                />
              </td>
            ))}
            <td style={{ whiteSpace: "nowrap" }}>
              <button onClick={() => save(b)}>保存权重</button>{" "}
              <button
                style={{ background: "var(--panel)", color: "var(--text)", border: "1px solid var(--line)" }}
                onClick={() => resetRow(b)} title="填入现网缺省值 40/20/5（仍需点保存）"
              >缺省</button>
            </td>
          </tr>
        );
      })}
      {!rows.length && <tr><td colSpan={6}>暂无楼栋</td></tr>}
      </tbody>
    </table>
    <p className="dispatch-deck-hint" style={{ marginTop: ".75rem" }}>
      缺省与现网一致：同向 {DEFAULT_WEIGHTS.same_dir_bonus} / 空闲 {DEFAULT_WEIGHTS.idle_bonus} /
      距离 {DEFAULT_WEIGHTS.distance_weight}（每楼层）。保存后再次进入仍显示已保存值；
      满员判定只看容量，不受权重影响。
    </p>
  </>);
}
