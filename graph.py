import collections.abc
import subprocess
import random as _random


class Link(frozenset):
    def __init__(self, *args):
        self.a, self.b = tuple(self)

    def __new__(cls, *args):
        if len(args) == 1:
            pair = set(args[0])
        else:
            pair = set(args)
        if len(pair) != 2:
            raise TypeError('Link expected two arguments or a pair')
        return super().__new__(cls, pair)

    def __repr__(self):
        return '(%r, %r)' % (self.a, self.b)

    def _render_link(self):
        return '    %s -- %s;' % (_dot_escape(self.a), _dot_escape(self.b))


class LinksView(collections.abc.MutableSet):
    def __init__(self, graph):
        self.graph = graph

    def __iter__(self):
        return iter(self.graph._links)

    def __len__(self):
        return len(self.graph._links)

    def __contains__(self, *args):
        try:
            return Link(*args) in self.graph._links
        except TypeError:
            return False

    def add(self, *args):
        self.graph.add_link(*args)

    def discard(self, *args):
        self.graph.discard_link(*args)

    def __repr__(self):
        return repr(self.graph._links)


class NodeLinksView(collections.abc.MutableSet):
    def __init__(self, graph, node):
        self.graph = graph
        self.node = node

    @property
    def _link_set(self):
        return self.graph._node_links.get(self.node, set())

    def __iter__(self):
        return iter(self._link_set)

    def __len__(self):
        return len(self._link_set)

    def __contains__(self, *args):
        try:
            return Link(*args) in self._link_set
        except TypeError:
            return False

    def add(self, *args):
        link = Link(*args)
        if not {self.node} <= link:
            raise ValueError('Expected link to node %r' % self.node)
        self.graph.add_link(link)

    def discard(self, *args):
        link = Link(*args)
        if link not in self._link_set:
            return
        self.graph.discard_link(link)

    def __repr__(self):
        return repr(self._link_set)


class NeighborhoodView(collections.abc.MutableSet):
    def __init__(self, graph, node):
        self.graph = graph
        self.node = node

    @property
    def _neighborhood(self):
        return self.graph._neighborhoods.get(self.node, set())

    def __iter__(self):
        return iter(self._neighborhood)

    def __len__(self):
        return len(self._neighborhood)

    def __contains__(self, neighbor):
        return neighbor in self._neighborhood

    def add(self, neighbor):
        self.graph.add(neighbor)
        if self.node == neighbor:
            return
        self.graph.add_link((self.node, neighbor))

    def discard(self, neighbor):
        if self.node == neighbor:
            raise ValueError('Cannot remove node from its own neighborhood')
        self.graph.discard_link((self.node, neighbor))

    def __repr__(self):
        return repr(self._neighborhood)


class NodeView:
    def __init__(self, graph, node):
        self.graph = graph
        self.node = node

    def __bool__(self):
        return self.node in self.graph

    def _get_links(self):
        return NodeLinksView(self.graph, self.node)

    def _set_links(self, links):
        if not self:
            return
        self.links.clear()
        for link in links:
            self.graph.add_link(link)

    def _get_neighborhood(self):
        return NeighborhoodView(self.graph, self.node)

    def _set_neighborhood(self, neighbors):
        if not self:
            return
        neighbors = set(neighbors)
        if self.node not in neighbors:
            raise ValueError('tried to remove node from its own neighborhood')
        self.links.clear()
        for node in neighbors:
            if node == self.node:
                continue
            self.graph.add_link(Link(self.node, node))

    links = property(_get_links, _set_links)
    neighborhood = property(_get_neighborhood, _set_neighborhood)

    def remove_self(self):
        self.graph.discard(self.node)

    def add_self(self):
        self.graph.add(self.node)

    def link_node(self, other):
        self.graph.add_link(Link(self.node, other))

    def unlink_node(self, other):
        self.graph.discard_link(Link(self.node, other))

    def __repr__(self):
        return '<Node view of %r on %r>' % (self.node, self.graph)


class Graph(collections.abc.MutableSet):
    def __init__(self, nodes=(), links=()):
        self._nodes = set()
        self._links = set()
        self._node_links = {}
        self._neighborhoods = {}
        self |= nodes
        for link in getattr(nodes, 'links', ()):
            self.add_link(link)
        for link in links:
            self.add_link(link)

    def _set_links(self, links):
        self.links.clear()
        for link in links:
            self.links.add(link)

    links = property(LinksView, _set_links)

    def __iter__(self):
        return iter(self._nodes)

    def __len__(self):
        return len(self._nodes)

    def __contains__(self, node):
        return node in self._nodes

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__)
        if not self._links:
            return '%s(%r)' % (self.__class__.__name__, self._nodes)
        return '%s(%r, %r)' % (self.__class__.__name__, self._nodes, self._links)

    def add(self, node):
        self._nodes.add(node)
        self._neighborhoods[node] = {node}

    def discard(self, node):
        for link in tuple(self._node_links.get(node, ())):
            self.discard_link(link)
        self._nodes.discard(node)
        del self._neighborhoods[node]

    def add_link(self, *args):
        link = Link(*args)
        for node in link:
            if node not in self:
                raise ValueError('Cannot link to missing node %r' % node)
        self._node_links.setdefault(link.a, set()).add(link)
        self._node_links.setdefault(link.b, set()).add(link)
        self._neighborhoods[link.a].add(link.b)
        self._neighborhoods[link.b].add(link.a)
        self._links.add(link)

    def discard_link(self, *args):
        link = Link(*args)
        _discard_and_del(self._node_links, link.a, link)
        _discard_and_del(self._node_links, link.b, link)
        self._neighborhoods[link.a].discard(link.b)
        self._neighborhoods[link.b].discard(link.a)
        self._links.discard(link)

    def link_set(self, node):
        return NodeLinksView(self, node)

    def neighborhood(self, node):
        return NeighborhoodView(self, node)

    def node_view(self, node):
        return NodeView(self, node)

    def render_dot(self, graph_name=None):
        lines = []

        if graph_name is None:
            lines.append('graph {')
        else:
            lines.append('graph %s {' % _dot_escape(graph_name))

        for node in self._nodes:
            lines.append('    %s;' % _dot_node(node))

        for link in self._links:
            lines.append(link._render_link())

        lines.append('}')
        lines.append('')

        return '\n'.join(lines)

    def save_dot(self, file, graph_name=None):
        do_close = False
        if isinstance(file, str):
            file = open(file, 'w')
            do_close = True
        file.write(self.render_dot(graph_name).encode('utf8'))
        file.flush()
        if do_close:
            file.close()

    def display(self, dot_args=['-Tx11'], dot_exec='dot'):
        dot = subprocess.Popen([dot_exec] + dot_args, stdin=subprocess.PIPE)
        dot.stdin.write(self.render_dot().encode('utf8'))
        dot.stdin.close()


def _discard_and_del(mapping, key, elem):
    collection = mapping.get(key, set())
    collection.discard(elem)
    if not collection:
        mapping.pop(key, None)


def _dot_node(node):
    if hasattr(node, '_dot_node'):
        return node._dot_node()
    return _dot_escape(node)


def _dot_escape(string):
    if hasattr(string, '_dot_repr'):
        return string._dot_repr()
    return '"%s"' % str(string).replace('\\', '\\\\').replace('"', '\\"')


def complete_graph(n):
    graph = Graph(range(n))
    for i in graph:
        for j in graph:
            if i != j:
                graph.add_link(i, j)
    return graph


def erdos_renyi(n, *, m=None, p=0.5, random=_random):
    'Random graph'
    graph = Graph(range(n))
    if m is not None:
        if m > n * (n - 1) // 2:
            raise ValueError('Requested number of links exceeds maximum')
        for _ in range(m):
            while True:
                left = random.randrange(0, n)
                right = random.randrange(0, n)
                while left == right:
                    right = random.randrange(0, n)
                link = Link(left, right)
                if link not in graph.links:
                    graph.add_link(link)
                    break
    else:
        if p <= 0:
            return graph
        if p >= 1:
            return complete_graph(n)
        for left in range(n):
            for right in range(n):
                if left == right:
                    continue
                if random.random() < p:
                    graph.add_link(Link(left, right))
    return graph
