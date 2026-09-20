import { useEffect, useState } from "react";
import { api } from "../api/client";
type B = {
  id: number;
  name: string;
  floors: number;
  same_dir_bonus: number;
  idle_bonus: number;
  distance_weight: number;
};
type Draft = { same_dir_bonus: string; idle_bonus: string; distance_weight: string };

function toDraft(b: B): Draft {
  return {
    same_dir_bonus: String(b.same_dir_bonus),
    idle_bonus: String(b.idle_bonus),
    distance_weight: String(b.distance_weight),
  };
}

export default function BuildingsPage() {
  const [rows, setRows] = useState<B[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [savedId, setSavedId] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const reload = () => api<B[]>("/buildings").then((bs) => {
    setRows(bs);
    const next: Record<number, Draft> = {};
    bs.forEach((b) => { next[b.id] = toDraft(b); });
    setDrafts(next);
  });
  useEffect(() => { reload(); }, []);
  function setField(id: number, key: keyof Draft, value: string) {
    setSavedId(null);
    setErr("");
    setDrafts((d) => ({ ...d, [id]: { ...d[id], [key]: value } }));
  }
  async function save(b: B) {
    const draft = drafts[b.id];
    const same_dir_bonus = Number(draft.same_dir_bonus);
    const idle_bonus = Number(draft.idle_bonus);
    const distance_weight = Number(draft.distance_weight);
    if ([same_dir_bonus, idle_bonus, distance_weight].some((v) => !Number.isFinite(v) || v < 0)) {
      setErr(`「${b.name}」权重需为不小于 0 的数字`);
      return;
    }
    setErr("");
    try {
      const updated = await api<B>(`/buildings/${b.id}/weights`, {
        method: "PUT",
        body: JSON.stringify({ same_dir_bonus, idle_bonus, distance_weight }),
      });
      setRows((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
      setDrafts((d) => ({ ...d, [updated.id]: toDraft(updated) }));
      setSavedId(b.id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }
  return (<>
    <h2>楼栋</h2>
    {err && <div className="err">{err}</div>}
    <table className="table">
      <thead><tr>
        <th>名称</th><th>楼层数</th><th>同向加分</th><th>空闲加分</th><th>距离权重</th><th></th>
      </tr></thead>
      <tbody>{rows.map(b => {
        const d = drafts[b.id] ?? toDraft(b);
        return (
          <tr key={b.id}>
            <td>{b.name}</td>
            <td className="mono">{b.floors}</td>
            <td><input type="number" min={0} step={1} className="weight-input mono"
              value={d.same_dir_bonus} onChange={e => setField(b.id, "same_dir_bonus", e.target.value)} /></td>
            <td><input type="number" min={0} step={1} className="weight-input mono"
              value={d.idle_bonus} onChange={e => setField(b.id, "idle_bonus", e.target.value)} /></td>
            <td><input type="number" min={0} step={0.5} className="weight-input mono"
              value={d.distance_weight} onChange={e => setField(b.id, "distance_weight", e.target.value)} /></td>
            <td>
              <button onClick={() => save(b)}>保存权重</button>
              {savedId === b.id && <span className="ok weight-saved">已保存</span>}
            </td>
          </tr>
        );
      })}</tbody>
    </table>
    <p className="settings-hint">缺省权重 同向+40 / 空闲+20 / 距离×5，与现网一致；修改后派工按新权重评分，满员判定不受影响。</p>
  </>);
}
