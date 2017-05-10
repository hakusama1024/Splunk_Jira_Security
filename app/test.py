import collections
def test(s):
    size = len(s)
    if size == 0 : return s
    stack = []
    counter = collections.Counter(s)
    se = set()
    for c in s:
        counter[c] -= 1
        if c in se:
            continue
        while stack and stack[-1] > c and counter[stack[-1]] != 0:
            se.remove(stack.pop())
        se.add(c)
        stack.append(c)
    print "".join(stack)

s = "bcacccdabcd"
test(s)

    
