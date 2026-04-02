import random
import scipy

class Distribution:
    def sample(self) -> float:
        pass

    def to_str(self) -> str:
        ""


class Linear(Distribution):
    def __init__(self, min: float, max: float):
        super().__init__()
        self.min = min
        self.max = max

    def sample(self):
        return random.uniform(self.min, self.max)
    
    def to_str(self):
        return f"Linear({self.min}, {self.max})"
    
class Normal(Distribution):
    def __init__(self, mean: float, standard_deviation: float):
        super().__init__()
        self.mean = mean
        self.standard_deviation = standard_deviation

    def sample(self):
        percentile = random.random()
        z_score = scipy.stats.norm.ppf(percentile)
        x = self.mean + z_score * self.standard_deviation
        return x
    
    def to_str(self):
        return f"Normal({self.mean}, {self.standard_deviation})"
