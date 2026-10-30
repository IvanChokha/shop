"use client";

// Error boundary сегмента: обязан быть клиентским компонентом.
export default function Error({ reset }) {
  return (
    <>
      <h1>Что-то пошло не так</h1>
      <p>Сервис временно недоступен. Повторите попытку через несколько секунд.</p>
      <button onClick={() => reset()}>Повторить</button>
    </>
  );
}
