import axios from "axios";

export interface Item {
  id: string;
  name: string;
}

export function fetchItems(): Promise<Item[]> {
  return axios.get<Item[]>("/api/items").then((resp) => resp.data);
}

export const fetchItem = (id: string) =>
  axios.get<Item>(`/api/items/${id}`).then((resp) => resp.data);
