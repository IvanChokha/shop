"use client";

import { useFormStatus } from "react-dom";

// Единственный клиентский компонент: блокирует кнопку, пока Server Action выполняется.
export default function SubmitButton({ children }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending}>
      {pending ? "Подождите…" : children}
    </button>
  );
}
