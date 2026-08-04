import { Item } from "../api";

export interface CardProps {
  item: Item;
  onSelect: (id: string) => void;
}

export function Card({ item, onSelect }: CardProps) {
  return (
    <div className="card" onClick={() => onSelect(item.id)}>
      <h3>{item.name}</h3>
    </div>
  );
}

export default Card;
