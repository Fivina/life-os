import { ArrowUp, BookOpen, CalendarDays, ChefHat, ListChecks, Plus, ShoppingCart } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

/** Shared text entry and contextual shortcuts for routed workspaces. */
export function PhengosAssistantBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  if (location.pathname === "/self/assistant") return null;

  const calendar = location.pathname === "/calendar";
  const kitchen = location.pathname === "/kitchen";
  const learning = location.pathname === "/learning";
  const placeholder = calendar ? "Add an event, or tell PHÉNGOS…" : kitchen
    ? "Add a meal, check my fridge, or ask PHÉNGOS…" : learning
      ? "Add study work, or ask PHÉNGOS…" : "Tell PHÉNGOS what you need…";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigate(`/self/assistant${draft.trim() ? `?q=${encodeURIComponent(draft.trim())}` : ""}`,
      { state: { phengosOriginLayer: "domain", phengosOriginGroup: calendar ? "Calendar" : kitchen ? "Home" : learning ? "Learning" : undefined } });
  }

  return <div className="pn-assistant-dock" role="region" aria-label="PHÉNGOS workspace input">
    <span className="pn-assistant-orb" aria-hidden="true" />
    <form onSubmit={submit}>
      <label className="phengos-sr-only" htmlFor="pn-assistant-input">Message for PHÉNGOS</label>
      <input id="pn-assistant-input" value={draft} onChange={event => setDraft(event.target.value)} placeholder={placeholder} autoComplete="off" />
      <button type="submit" aria-label="Open assistant with message" title="Send to PHÉNGOS"><ArrowUp size={18} /></button>
    </form>
    <div className="pn-assistant-tools">
      {calendar && <>
        <Link to="/calendar#add-intention" title="New intention" aria-label="New intention"><ListChecks size={18} /></Link>
        <Link to="/calendar#daily-list" title="Planning controls" aria-label="Planning controls"><CalendarDays size={18} /></Link>
      </>}
      {kitchen && <>
        <Link to="/kitchen#planned-meals" title="Planned meals" aria-label="Planned meals"><ChefHat size={18} /></Link>
        <Link to="/kitchen#shopping" title="Shopping list" aria-label="Shopping list"><ShoppingCart size={18} /></Link>
      </>}
      {learning && <Link to="/learning#study-log" title="Study log" aria-label="Study log"><BookOpen size={18} /></Link>}
    </div>
    {calendar && <Link className="pn-assistant-primary" to="/calendar#add-commitment"><Plus size={18} />Add Event</Link>}
    {kitchen && <Link className="pn-assistant-primary" to="/kitchen#chef-workspace"><Plus size={18} />Open Chef</Link>}
  </div>;
}
