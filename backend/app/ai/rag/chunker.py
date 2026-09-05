from dataclasses import dataclass
@dataclass
class TextPart:text:str;page:int|None=None
def chunk_parts(parts:list[TextPart],size:int,overlap:int):
 out=[]
 for part in parts:
  text=part.text.strip();start=0
  while start<len(text):
   end=min(start+size,len(text));cut=end
   if end<len(text):
    boundary=max(text.rfind("\n",start,end),text.rfind(". ",start,end));cut=boundary+1 if boundary>start+size//2 else end
   value=text[start:cut].strip()
   if value:out.append((value,{"page":part.page}))
   if cut>=len(text):break
   start=max(start+1,cut-overlap)
 return out
