import { useState } from "react";

export interface Props {
  title: string;
}

export class Button {
  render(label: string): string {
    return label;
  }

  onClick() {
    this.render("x");
  }
}

export default function App() {
  const [count, setCount] = useState(0);
  return count;
}
