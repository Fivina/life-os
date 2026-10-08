import { CalendarSync, Lock, LockOpen, RefreshCw } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../services/api";


export function StandingRulesPanel() {
  const queryClient = useQueryClient();
  const rules = useQuery({ queryKey: ["standing_calendar_rules"], queryFn: api.standingCalendarRules });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["standing_calendar_rules"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    queryClient.invalidateQueries({ queryKey: ["current-plan"] });
  };
  const sync = useMutation({ mutationFn: api.syncStandingCalendarRule, onSuccess: refresh });
  const toggle = useMutation({ mutationFn: ({ id, enabled, version }: { id: string; enabled: boolean; version: number }) => api.setStandingCalendarRuleEnabled(id, enabled, version), onSuccess: refresh });

  return <section className="content-band standing-rules" id="calendar-utilities">
    <div className="section-header"><h2>Standing Calendar Rules</h2><CalendarSync size={18} /></div>
    {(rules.data ?? []).map((rule) => <div className="standing-rule-row" key={rule.id}>
      <div>
        <strong>{rule.name}</strong>
        <span>{rule.last_sync_status} · every {rule.sync_interval_days} days</span>
        <small>{rule.last_sync_at ? `Last synced ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(rule.last_sync_at))}` : "Not synced yet"}</small>
        {rule.last_error ? <small className="error">{rule.last_error}</small> : null}
      </div>
      <div className="standing-rule-actions">
        <button className="icon-button" type="button" title={rule.enabled ? "Disable rule" : "Enable rule"} aria-label={rule.enabled ? "Disable Beşiktaş fixture rule" : "Enable Beşiktaş fixture rule"} onClick={() => toggle.mutate({ id: rule.id, enabled: !rule.enabled, version: rule.version })}>{rule.enabled ? <Lock size={16} /> : <LockOpen size={16} />}</button>
        <button className="icon-button" type="button" title="Sync fixtures" aria-label="Sync Beşiktaş fixtures" onClick={() => sync.mutate(rule.id)} disabled={!rule.enabled || sync.isPending}><RefreshCw size={16} /></button>
      </div>
    </div>)}
    {sync.data ? <p className={`status-text ${sync.data.status === "FAILED" ? "error" : "success"}`}>{sync.data.status === "SUCCESS" ? `${sync.data.created} created, ${sync.data.updated} updated, ${sync.data.noop} unchanged.` : sync.data.error}</p> : null}
  </section>;
}
