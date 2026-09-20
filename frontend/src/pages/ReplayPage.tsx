import { useEffect, useState } from "react";
import { api } from "../api/client";
type Log = {
  id: number;
  call_id: number;
  car_id: number | null;
  detail: string;
  weight_summary: string;
  same_dir_bonus: number | null;
  idle_bonus: number | null;
  distance_weight: number | null;
  created_at: string;
};
export default function ReplayPage() {
  const [rows, setRows] = useState<Log[]>([]);
  useEffect(() => { api<Log[]>("/replay").then(setRows); }, []);
  return (<>
    <h2>回放</h2>
    <table className="table"><thead><tr><th>时间</th><th>呼梯</th><th>轿厢</th><th>本次权重</th><th>详情</th></tr></thead>
    <tbody>{rows.map(l => <tr key={l.id}>
      <td className="mono">{new Date(l.created_at).toLocaleString()}</td>
      <td>#{l.call_id}</td>
      <td>{l.car_id ?? "—"}</td>
      <td className="mono weight-cell" title="本次派工使用的权重快照">
        {l.weight_summary
          || (l.same_dir_bonus != null
            ? `权重 同向+${l.same_dir_bonus}/空闲+${l.idle_bonus}/距离×${l.distance_weight}`
            : "—")}
      </td>
      <td>{l.detail}</td>
    </tr>)}</tbody></table>
  </>);
}
