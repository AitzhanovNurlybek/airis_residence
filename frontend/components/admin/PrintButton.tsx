"use client";

/**
 * Кнопка печати счёта.
 *
 * Отдельный маленький клиентский компонент, а не часть серверной страницы:
 * window.print() существует только в браузере, а страница счёта сама по себе
 * серверная — так быстрее открывается и не мигает пустым перед заполнением.
 *
 * Печать, а не «Отправить» — специально. Отправка компании сейчас происходит
 * тем же способом, каким менеджер обычно списывается с ней (WhatsApp, почта,
 * что угодно), а не через наш сайт. Кнопка печати даёт готовый документ:
 * браузер умеет сохранить такую страницу как PDF в диалоге печати, дальше
 * это обычный файл, который прикладывают куда угодно.
 */
export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="no-print inline-flex h-11 items-center justify-center gap-2 rounded-full bg-linear-to-b from-wine-500 to-wine-700 px-6 text-sm font-medium text-white transition-all hover:from-wine-400 hover:to-wine-600"
    >
      Печать / сохранить как PDF
    </button>
  );
}
