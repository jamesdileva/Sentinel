import { useState, useEffect } from "react";
import { Card } from "./components/Card";
import { fetchItems, Item } from "./api";

export interface DashboardProps {
  title: string;
  items: Item[];
}

export type ViewMode = "grid" | "list";

export default function Dashboard({ title, items }: DashboardProps) {
  const [mode, setMode] = useState<ViewMode>("grid");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchItems().then(() => setLoaded(true));
  }, []);

  function handleSelect(id: string) {
    console.log("selected", id);
  }

  return (
    <div className="dashboard">
      <h1>{title}</h1>
      {items.map((item) => (
        <Card key={item.id} item={item} onSelect={handleSelect} />
      ))}
      <StatusText loaded={loaded} />
    </div>
  );
}

function StatusText({ loaded }: { loaded: boolean }) {
  return <span>{loaded ? "loaded" : "loading"}</span>;
}
