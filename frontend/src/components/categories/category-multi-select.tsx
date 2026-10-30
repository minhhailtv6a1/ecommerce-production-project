import type { Category } from "@/types/category";

export function CategoryMultiSelect({
  categories,
  selected,
  onChange,
  compact = false,
}: {
  categories: Category[];
  selected: string[];
  onChange: (next: string[]) => void;
  compact?: boolean;
}) {
  function toggle(id: string) {
    onChange(
      selected.includes(id)
        ? selected.filter((value) => value !== id)
        : [...selected, id],
    );
  }

  return (
    <div className={compact ? "category-list compact" : "category-list"}>
      {categories.map((category) => (
        <label className="check-row" key={category.id}>
          <input
            type="checkbox"
            checked={selected.includes(category.id)}
            onChange={() => toggle(category.id)}
          />
          <span className="check-copy">
            <span>{category.name}</span>
            <small>
              {category.id} · {category.product_count} sản phẩm
            </small>
          </span>
        </label>
      ))}
    </div>
  );
}
