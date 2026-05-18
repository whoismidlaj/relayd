import React, { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";

export default function TagsInput({ value, onChange, placeholder, suggestions = [] }) {
  const [input, setInput] = useState("");
  const tags = value ? value.split(",").map(t => t.trim()).filter(Boolean) : [];

  const addTag = (tag) => {
    if (!tag) return;
    if (!tags.includes(tag)) onChange([...tags, tag].join(", "));
    setInput("");
  };

  const removeTag = (tagToRemove) => {
    onChange(tags.filter(t => t !== tagToRemove).join(", "));
  };

  return (
    <div className="space-y-2">
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {tags.map((tag, i) => (
            <Badge key={i} variant="secondary" className="flex items-center gap-1 px-2 py-0.5 text-xs">
              {tag}
              <button type="button" onClick={() => removeTag(tag)} className="text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            addTag(input.trim());
          }
        }}
        placeholder={tags.length === 0 ? placeholder : "Type and press Enter to add..."}
      />
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          <span className="text-[10px] text-muted-foreground self-center mr-1">Suggestions:</span>
          {suggestions.filter(s => !tags.includes(s)).map(s => (
            <Badge key={s} variant="outline" className="cursor-pointer text-[10px] opacity-60 hover:opacity-100 transition-opacity" onClick={() => addTag(s)}>
              + {s}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
