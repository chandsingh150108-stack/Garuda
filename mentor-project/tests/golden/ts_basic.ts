import React from "react";
import { useState, useEffect as fx } from "./hooks";
import * as utils from "../lib/utils";
import { x } from "@/lib/x";

export function greet(name: string): string {
  const upper = name.toUpperCase();
  return upper;
}

export const helper = (a: number) => a + 1;

class Store {
  load(id: number) {
    return id;
  }
}
