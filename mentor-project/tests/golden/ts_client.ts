import axios from "axios";

export async function login(email: string, password: string) {
  const res = await fetch("/api/login/access-token", {
    method: "POST",
  });
  return res;
}

export async function createItem(data: unknown) {
  const res = await axios.post("/api/items", data);
  return res.data;
}

export function localOnly(x: number) {
  return compute(x) + 1;
}
